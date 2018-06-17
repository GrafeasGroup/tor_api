import os
import sqlite3

import pytest
from tor_api.main import DatabaseHandler


class TestDB(object):

    test_db_addr = './tor_api/tests/test_db.db'
    secondary_test_db_addr = './tor_api/tests/test_db_the_second.db'

    log_data = {
        'api_key': '1234',
        'ip_address': '1.1.1.1',
        'endpoint': '/snarfleblat',
        'request_data': {
            'the_goodest_of_boys': 'Kuma',
            'best_doggo': 'Kuma'
        }
    }

    user_data = {
        'api_key': 'asdf',
        'name': 'Sleepy',
        'is_admin': False,
        'admin_api_key': '1234',
    }

    db = None  # overwritten by fixture
    test_db = None  # overwritten by fixture

    @pytest.fixture(autouse=True)
    def setup_db(self):
        # setup
        self.db = DatabaseHandler(db_name=self.secondary_test_db_addr)
        # call
        yield
        # teardown
        del self.db
        try:
            os.remove(self.secondary_test_db_addr)
        except OSError:
            pass

    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        self.test_db = DatabaseHandler(db_name=self.test_db_addr)

    def test_db_file_creation(self):
        assert os.path.exists(self.secondary_test_db_addr)

    def test_db_tables(self):
        # verify that all the tables are there
        con = sqlite3.connect(self.secondary_test_db_addr)
        cursor = con.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        assert tables == [('users',), ('log',)]

    def test_db_user_table(self):
        con = sqlite3.connect(self.secondary_test_db_addr)
        cursor = con.cursor()
        cursor.execute('SELECT * FROM users')
        names = list(map(lambda x: x[0], cursor.description))

        assert names == [
            'api_key',
            'name',
            'is_admin',
            'date_granted',
            'authed_by'
        ]

    def test_db_log_table(self):
        con = sqlite3.connect(self.secondary_test_db_addr)
        cursor = con.cursor()

        cursor.execute('SELECT * FROM log')
        names = list(map(lambda x: x[0], cursor.description))

        assert names == [
            'api_key',
            'ip_address',
            'endpoint',
            'date',
            'request_data'
        ]

    def test_write_log_entry(self):
        self.db.write_log_entry(self.log_data)
        con = sqlite3.connect(self.secondary_test_db_addr)
        cursor = con.cursor()
        cursor.execute('SELECT * FROM log')
        data = cursor.fetchone()
        assert data == (
            '1234',
            '1.1.1.1',
            '/snarfleblat',
            '{}'.format(data[3]),  # add in the server time / date from the db
            "{'the_goodest_of_boys': 'Kuma', 'best_doggo': 'Kuma'}",
        )

    def test_write_user_entry(self):
        self.db.write_user_entry(self.user_data)
        con = sqlite3.connect(self.secondary_test_db_addr)
        cursor = con.cursor()
        cursor.execute('SELECT * FROM users')
        data = cursor.fetchone()
        assert data == (
            'asdf',
            'Sleepy',
            0,
            '{}'.format(data[3]),  # add in the server time / date from the db
            '1234'
        )

    def test_me(self):
        con = sqlite3.connect(self.test_db_addr)
        cursor = con.cursor()
        cursor.execute('SELECT * FROM users')
        data = cursor.fetchone()
        assert data == (
            'asdf',
            'Dopey',
            1,
            '2018-06-16T16:37:58.866558',
            '1234'
        )

    def test_is_admin(self):
        assert self.test_db.is_admin('asdf') is True
        assert self.test_db.is_admin('1234') is False
        assert self.test_db.is_admin('qwer') is False

    def test_validate_key(self):
        assert self.test_db.validate_key('asdf') is True
        assert self.test_db.validate_key('1234') is False
        assert self.test_db.validate_key('qwer') is True

    def test_revoke_key(self):
        self.test_db.revoke_key('pppppp')
        # validate the user does not exist
        result = self.test_db.get_self('pppppp')
        assert result is None

        #  add the dummy key
        self.test_db.write_user_entry(
            {
                'api_key': 'pppppp',
                'name': 'Testy McTesterson',
                'is_admin': False,
                'admin_api_key': '1234'
            }
        )
        # validate that it got saved
        result = self.test_db.get_self('pppppp')
        assert result == {
            'api_key': 'pppppp',
            'username': 'Testy McTesterson',
            'is_admin': False,
            # use returned date / time
            'date_granted': '{}'.format(result['date_granted']),
            'authorized_by': '1234'
        }

        self.test_db.revoke_key('pppppp')
        # validate the user does not exist now
        result = self.test_db.get_self('pppppp')
        assert result is None
