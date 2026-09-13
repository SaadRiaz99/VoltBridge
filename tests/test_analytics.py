from datetime import datetime, timedelta, timezone
import pytest
from electrical_mcp.models import Device, Settings, Reading
from electrical_mcp.service import Operations
from electrical_mcp.connectors import DeviceUnavailable

START, END = '2020-01-01T00:00:00Z', '2100-01-01T00:00:00Z'


def setup(tmp_path, connector, company='alpha'):
    return Operations(Settings(database=str(tmp_path/'analytics.db'), company_id=company,
        role='viewer', devices=[Device(id=d, name=d, connector='http', base_url='http://localhost')
                                for d in ['a', 'b', 'c']]), {'http': connector})


class Telemetry:
    def __init__(self, mode='good'):
        self.mode = mode
        self.calls = []

    async def read(self, device):
        self.calls.append(device.id)
        if device.id == 'c' or (device.id == 'b' and self.mode == 'offline'):
            raise DeviceUnavailable('Offline')
        now = datetime.now(timezone.utc)
        metric = 'current' if device.id == 'b' and self.mode == 'missing' else 'power'
        delay = 300 if self.mode == 'stale' else 10 if self.mode == 'skew' else 0
        return [Reading(metric=metric, value=10 if device.id == 'a' else 4,
            unit='A' if metric == 'current' else 'kW',
            timestamp=now-timedelta(seconds=delay if device.id == 'b' else 0),
            simulated=device.id == 'b' and self.mode == 'mixed')]


async def test_fleet_partial_failure_and_limits(tmp_path):
    ops = setup(tmp_path, Telemetry('stale'))
    result = await ops.fleet_health()
    assert result['counts'] == {'online': 1, 'degraded': 1, 'unavailable': 1}
    assert result['checked'] == result['total_configured'] == 3
    assert not result['truncated']
    limited = await ops.fleet_health(1)
    assert limited['truncated'] and limited['checked'] == 1
    with pytest.raises(ValueError):
        await ops.fleet_health(51)


async def test_compare_success_and_validation(tmp_path):
    connector = Telemetry()
    ops = setup(tmp_path, connector)
    result = await ops.compare_devices('a', 'b', 'power')
    assert result['comparable'] and result['difference_first_minus_second'] == 6
    assert result['unit'] == 'kW'
    connector.calls.clear()
    with pytest.raises(ValueError):
        await ops.compare_devices('a', 'foreign-device', 'power')
    assert connector.calls == []
    with pytest.raises(ValueError):
        await ops.compare_devices('a', 'a', 'power')


@pytest.mark.parametrize('mode', ['stale', 'skew', 'mixed', 'offline', 'missing'])
async def test_compare_rejects_incomparable_samples(tmp_path, mode):
    result = await setup(tmp_path, Telemetry(mode)).compare_devices('a', 'b', 'power')
    assert not result['comparable']
    assert result['difference_first_minus_second'] is None
    assert result['reason']


def test_statistics_values_quality_simulation_limits_and_tenants(tmp_path):
    ops = setup(tmp_path, Telemetry())
    now = datetime.now(timezone.utc)
    rows = []
    for value, simulated, usable in [(2, False, True), (6, False, True),
                                     (100, False, False), (50, True, True)]:
        rows.append({'metric': 'power', 'value': value, 'unit': 'kW',
            'timestamp': now.isoformat(), 'simulated': simulated, 'usable': usable})
    ops.store.save_readings('alpha', 'a', rows)
    result = ops.measurement_statistics('a', 'power', START, END)
    assert result['sample_count'] == 4 and result['excluded_count'] == 1
    assert result['groups']['non_simulated']['mean'] == 4
    assert result['groups']['non_simulated']['minimum'] == 2
    assert result['groups']['non_simulated']['maximum'] == 6
    assert result['groups']['simulated']['mean'] == 50
    assert not result['truncated']
    limited = ops.measurement_statistics('a', 'power', START, END, 2)
    assert limited['sample_count'] == 2 and limited['truncated']
    assert limited['groups']['non_simulated']['mean'] is None
    other = setup(tmp_path, Telemetry(), company='beta').measurement_statistics('a', 'power', START, END)
    assert other['sample_count'] == 0 and other['groups']['non_simulated']['mean'] is None
    with pytest.raises(ValueError):
        ops.measurement_statistics('a', 'power', '2026-01-01', END)
    with pytest.raises(ValueError):
        ops.measurement_statistics('a', 'power', END, START)
    with pytest.raises(ValueError):
        ops.measurement_statistics('a', 'invalid', START, END)
