import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from electrical_mcp.service import Operations
from electrical_mcp.models import Settings, Device, Reading
from electrical_mcp.store import Store
from electrical_mcp.alerts import AlertManager, AlertRule, AlertCondition, AlertState
from electrical_mcp.device_groups import DeviceGroupManager
from electrical_mcp.scheduler import TaskScheduler, TaskType, TaskStatus

START, END = '2020-01-01T00:00:00Z', '2100-01-01T00:00:00Z'


def ops(tmp_path, role='maintenance', company='alpha', connector=None):
    return Operations(Settings(database=str(tmp_path/'v04.db'), company_id=company, role=role,
        devices=[Device(id='motor-3', name='Motor')]), {'simulator': connector} if connector else None)


async def test_cached_reads_recheck_freshness_without_network(tmp_path):
    operator = ops(tmp_path)
    assert operator.latest_measurements('motor-3')['readings'] == []
    await operator.read('motor-3')
    class Fail:
        async def read(self, device):
            pytest.fail('Cached reads must not access gateway')
    operator.connectors['simulator'] = Fail()
    cached = operator.latest_measurements('motor-3')
    assert cached['source'] == 'stored_history' and not cached['gateway_contacted']
    assert len(cached['readings']) == 5
    assert all(r['usable'] and r['simulated'] for r in cached['readings'])
    operator.devices['motor-3'].stale_after_seconds = 1
    with operator.store.connect() as db:
        import json
        rows = db.execute('SELECT id,payload FROM readings').fetchall()
        for row in rows:
            payload = json.loads(row['payload'])
            payload['timestamp'] = (datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()
            db.execute('UPDATE readings SET timestamp=?,payload=? WHERE id=?',
                       (payload['timestamp'], json.dumps(payload), row['id']))
    assert all(not r['usable'] and r['stale'] and r['usable_at_collection']
               for r in operator.latest_measurements('motor-3')['readings'])
    assert ops(tmp_path, company='beta').latest_measurements('motor-3')['readings'] == []


async def test_quality_report_limits_and_empty_data(tmp_path):
    operator = ops(tmp_path)
    assert operator.data_quality_report('motor-3', START, END)['usable_percent'] is None
    await operator.read('motor-3')
    result = operator.data_quality_report('motor-3', START, END, 2)
    assert result['sample_count'] == 2 and result['truncated']
    assert result['usable_percent'] == 100 and result['simulated_count'] == 2
    assert result['quality_counts']['good'] == 2
    assert ops(tmp_path, company='beta').data_quality_report('motor-3', START, END)['sample_count'] == 0
    with pytest.raises(ValueError):
        operator.data_quality_report('motor-3', END, START)


def test_draft_lookup_permissions_and_company_isolation(tmp_path):
    operator = ops(tmp_path)
    draft = operator.draft('motor-3', 'Inspect', 'retry')
    assert operator.maintenance_draft(draft['id']) == draft
    with pytest.raises(ValueError):
        ops(tmp_path, company='beta').maintenance_draft(draft['id'])
    with pytest.raises(PermissionError):
        ops(tmp_path, role='viewer').maintenance_draft(draft['id'])


def test_groups_survive_restart_with_children_and_company_scope(tmp_path):
    store = Store(str(tmp_path/'groups.db'))
    first = DeviceGroupManager(store, 'alpha')
    first.create_group('plant', 'Plant')
    first.create_group('line', 'Line', parent_group_id='plant')
    first.add_device_to_group('motor-3', 'line')
    reopened = DeviceGroupManager(store, 'alpha')
    assert reopened.get_group_tree()['groups'][0]['children'][0]['device_ids'] == ['motor-3']
    assert DeviceGroupManager(store, 'beta').list_groups() == []


async def test_tasks_persist_enum_state_and_zero_threshold(tmp_path):
    operator = ops(tmp_path)
    scheduler = TaskScheduler(operator, operator.store, 'alpha')
    scheduler.create_task('zero', 'Zero threshold', TaskType.THRESHOLD_CHECK, interval_seconds=60,
        config={'device_id':'motor-3','metric':'power','maximum':0,'unit':'kW'})
    reopened = TaskScheduler(operator, operator.store, 'alpha')
    assert reopened.get_task('zero').task_type is TaskType.THRESHOLD_CHECK
    execution = await reopened.run_task_now('zero')
    assert execution.status is TaskStatus.COMPLETED
    assert execution.result['result'] == 'above_limit'
    again = TaskScheduler(operator, operator.store, 'alpha')
    assert again.get_task('zero').run_count == 1
    assert again.get_task('zero').last_status is TaskStatus.COMPLETED
    assert TaskScheduler(operator, operator.store, 'beta').list_tasks() == []
    with pytest.raises(ValueError, match='Cron'):
        scheduler.create_task('cron', 'Cron', TaskType.DEVICE_READ, schedule_cron='*/5 * * * *')


def test_alerts_persist_and_cooldown_is_per_device(tmp_path):
    store = Store(str(tmp_path/'alerts.db'))
    manager = AlertManager(store, 'alpha')
    manager.add_rule(AlertRule('r', 'High', 'temperature', AlertCondition.ABOVE, threshold_value=45))
    samples = [{'metric':'temperature','value':48,'usable':True,'simulated':True}]
    a = manager.evaluate_rules('a', samples)[0]
    assert manager.evaluate_rules('b', samples)
    assert not manager.evaluate_rules('a', samples)
    reopened = AlertManager(store, 'alpha')
    assert len(reopened.list_rules()) == 1 and len(reopened.get_active_alerts()) == 2
    assert not reopened.evaluate_rules('a', samples)
    assert reopened.acknowledge_alert(a.alert_id, 'operator')
    assert AlertManager(store, 'alpha').get_active_alerts(device_id='a')[0].state is AlertState.ACKNOWLEDGED
    reopened.resolve_alert(a.alert_id)
    assert not AlertManager(store, 'alpha').get_active_alerts(device_id='a')
    assert AlertManager(store, 'beta').list_rules() == []


def test_between_alert_semantics_and_bad_data():
    manager = AlertManager()
    manager.add_rule(AlertRule('r', 'Between', 'temperature', AlertCondition.BETWEEN,
                               threshold_value=10, threshold_value_upper=20, cooldown_seconds=0))
    assert not manager.evaluate_rules('a', [{'metric':'temperature','value':15,'usable':False}])
    assert manager.evaluate_rules('a', [{'metric':'temperature','value':15,'usable':True}])
    assert not manager.evaluate_rules('a', [{'metric':'temperature','value':30,'usable':True}])
    with pytest.raises(ValueError):
        manager.add_rule(AlertRule('bad', 'Unsupported', 'temperature', AlertCondition.RATE_OF_CHANGE,
                                  threshold_value=2))


async def test_gateway_budget_shared_across_overlapping_fleet_checks(tmp_path):
    class Slow:
        active = 0
        peak = 0
        async def read(self, device):
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                await asyncio.sleep(.01)
                return [Reading(metric='power', value=1, unit='kW', timestamp=datetime.now(timezone.utc))]
            finally:
                self.active -= 1
    slow = Slow()
    operator = Operations(Settings(database=str(tmp_path/'parallel.db'), devices=[
        Device(id=f'd{i}',name=f'Device {i}') for i in range(6)]), {'simulator':slow})
    results = await asyncio.gather(operator.fleet_health(), operator.fleet_health())
    assert all(r['checked'] == 6 for r in results)
    assert 1 < slow.peak <= 4 and slow.active == 0


def test_metric_history_query_uses_covering_order_index(tmp_path):
    store = Store(str(tmp_path/'index.db'))
    with store.connect() as db:
        plan = db.execute('''EXPLAIN QUERY PLAN SELECT payload FROM readings
            WHERE company=? AND device=? AND metric=? AND timestamp>=? AND timestamp<=?
            ORDER BY timestamp DESC, id DESC LIMIT ?''', ('a','d','power',START,END,10)).fetchall()
    detail = ' '.join(row['detail'] for row in plan)
    assert 'readings_metric_lookup' in detail
    assert 'TEMP B-TREE' not in detail
