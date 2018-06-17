from unittest.mock import patch


@patch('tor_core.initialize.configure_redis', return_value=None)
class TestTools(object):
    def test_log(self, patched_redis):
        assert 1 is 1