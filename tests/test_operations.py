from datetime import datetime, timedelta, timezone
import httpx
import pytest
from electrical_mcp.models import Device, Reading, Settings
from electrical_mcp.connectors import HttpConnector, DeviceUnavailable
from electrical_mcp.service import Operations


def operations(tmp_path, role='maintenance', company='alpha', connectors=None):
    return Operations(Settings(database=str(tmp_path/'test.db'), role=role, company_id=company,
                               devices=[Device(id='motor-3', name='Motor')]), connectors)


async def test_read_threshold_and_history(tmp_path):
    ops = operations(tmp_path)
    result = await ops.threshold('motor-3', 'temperature', 45, 'degC')
    assert result['result'] == 'above_limit'
    assert result['reading']['simulated'] is True
    now = datetime.now(timezone.utc)
    history = ops.history('motor-3', (now-timedelta(minutes=1)).isoformat(),
                         (now+timedelta(minutes=1)).isoformat())
    assert len(history) == 5
    assert {r['unit'] for r in history} == {'V', 'A', 'kW', 'kWh', 'degC'}
    with pytest.raises(ValueError):
        await ops.threshold('motor-3', 'temperature', 45, 'F')


def test_draft_retry_and_conflict(tmp_path):
    ops = operations(tmp_path)
    first = ops.draft('motor-3', 'Inspect bearing', 'key-1')
    assert ops.draft('motor-3', 'Inspect bearing', 'key-1')['id'] == first['id']
    assert first['sent_to_external_system'] is False
    with pytest.raises(ValueError):
        ops.draft('motor-3', 'Different issue', 'key-1')
    assert len(ops.drafts()) == 1


async def test_company_boundaries_and_permissions(tmp_path):
    alpha = operations(tmp_path)
    beta = operations(tmp_path, company='beta')
    alpha.draft('motor-3', 'Private issue', 'same-key')
    await alpha.read('motor-3')
    assert beta.drafts() == []
    assert beta.history('motor-3', '2020-01-01T00:00:00Z', '2100-01-01T00:00:00Z') == []
    viewer = operations(tmp_path, role='viewer')
    with pytest.raises(PermissionError):
        viewer.draft('motor-3', 'Issue', 'k')
    with pytest.raises(PermissionError):
        viewer.audit()
    assert any(r['outcome'] == 'denied' for r in operations(tmp_path, role='admin').audit())
    with pytest.raises(ValueError):
        await alpha.read('../other-device')


@pytest.mark.parametrize('seconds,quality', [(3600, 'good'), (-3600, 'good'), (0, 'bad'), (0, 'uncertain')])
async def test_unusable_readings_cannot_pass_threshold(tmp_path, seconds, quality):
    class BadTelemetry:
        async def read(self, device):
            return [Reading(metric='temperature', value=20, unit='degC', quality=quality,
                            timestamp=datetime.now(timezone.utc)-timedelta(seconds=seconds))]
    ops = operations(tmp_path, connectors={'simulator': BadTelemetry()})
    assert (await ops.threshold('motor-3', 'temperature', 45, 'degC'))['result'] == 'unknown'
    assert (await ops.status('motor-3'))['status'] == 'degraded'


def payload(unit='kW'):
    return {'readings': [{'metric': 'power', 'value': 3.2, 'unit': unit,
                         'timestamp': datetime.now(timezone.utc).isoformat(), 'quality': 'good'}]}


async def test_http_contract():
    def handler(request):
        assert request.url.path == '/devices/meter-1/measurements'
        return httpx.Response(200, json=payload())
    connector = HttpConnector(httpx.MockTransport(handler))
    device = Device(id='meter-1', name='Meter', connector='http', base_url='https://gateway.example')
    assert (await connector.read(device))[0].value == 3.2


@pytest.mark.parametrize('response', [
    httpx.Response(200, json=payload('watts')),
    httpx.Response(200, json={'readings': []}),
    httpx.Response(200, text='not-json'),
    httpx.Response(200, content=b'x'*65537),
    httpx.Response(302, headers={'Location': 'https://elsewhere.example'}),
    httpx.Response(500, text='private upstream message'),
])
async def test_bad_gateway_responses_are_rejected(response):
    connector = HttpConnector(httpx.MockTransport(lambda request: response))
    with pytest.raises(DeviceUnavailable) as error:
        await connector.read(Device(id='meter', name='Meter', connector='http', base_url='https://gateway.example'))
    assert 'private upstream' not in str(error.value)


async def test_network_retry_is_bounded():
    attempts = []
    def unavailable(request):
        attempts.append(request)
        raise httpx.ConnectError('secret endpoint', request=request)
    connector = HttpConnector(httpx.MockTransport(unavailable))
    with pytest.raises(DeviceUnavailable):
        await connector.read(Device(id='meter', name='Meter', connector='http', base_url='https://gateway.example'))
    assert len(attempts) == 2


async def test_tokens_require_https(monkeypatch):
    monkeypatch.setenv('DEVICE_TOKEN', 'do-not-send')
    connector = HttpConnector(httpx.MockTransport(lambda request: pytest.fail('Must not send token')))
    with pytest.raises(DeviceUnavailable, match='HTTPS'):
        await connector.read(Device(id='meter', name='Meter', connector='http',
                                   base_url='http://gateway.example', token_env='DEVICE_TOKEN'))


async def test_offline_status(tmp_path):
    class Offline:
        async def read(self, device):
            raise DeviceUnavailable('Gateway failed')
    ops = operations(tmp_path, connectors={'simulator': Offline()})
    assert (await ops.status('motor-3'))['status'] == 'unavailable'
    assert operations(tmp_path, role='admin').audit()[1]['outcome'] == 'failed'
