import unittest
from unittest.mock import Mock

from controller.presence import BrowserPresence


class BrowserPresenceTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.release, self.maintain = Mock(), Mock()
        self.presence = BrowserPresence(self.release, self.maintain, lambda:self.now)
        self.first, self.second = 'a'*32, 'b'*32

    def tick(self, seconds):
        self.now += seconds
        self.presence.tick()

    def test_headless_app_is_not_stopped_without_any_browser_registration(self):
        self.tick(1000)
        self.release.assert_not_called()
        self.maintain.assert_called_once()

    def test_only_the_last_closed_tab_releases_resources_after_the_grace_period(self):
        self.presence.pulse(self.first, 1)
        self.presence.pulse(self.second, 1)
        self.presence.pulse(self.first, 2, True)
        self.tick(35)
        self.release.assert_not_called()
        self.presence.pulse(self.second, 2, True)
        self.tick(0); self.tick(4)
        self.release.assert_not_called()
        self.tick(1); self.tick(10)
        self.release.assert_called_once()

    def test_refresh_reconnect_and_background_heartbeats_preserve_resources(self):
        self.presence.pulse(self.first, 1)
        self.presence.pulse(self.first, 2, True)
        self.tick(1)
        self.tick(3)
        self.presence.pulse(self.second, 1)
        for i in range(2, 10):
            self.tick(60)
            self.presence.pulse(self.second, i)
        self.release.assert_not_called()

    def test_crash_expires_the_lease_and_later_reopening_arms_cleanup_again(self):
        self.presence.pulse(self.first, 1)
        self.tick(299)
        self.release.assert_not_called()
        self.tick(1); self.tick(5)
        self.release.assert_called_once()
        self.presence.pulse(self.second, 1)
        self.presence.pulse(self.second, 2, True)
        self.tick(0); self.tick(5)
        self.assertEqual(self.release.call_count, 2)

    def test_out_of_order_heartbeat_cannot_undo_close_and_failed_cleanup_retries(self):
        self.presence.pulse(self.first, 2, True)
        self.presence.pulse(self.first, 1)
        self.tick(0)
        self.release.side_effect = ValueError('Setup still finishing')
        with self.assertRaises(ValueError): self.tick(5)
        self.release.side_effect = None
        self.tick(5)
        self.assertEqual(self.release.call_count, 2)
        self.assertTrue(self.presence.released)

    def test_invalid_heartbeats_are_rejected(self):
        for identifier, sequence, closing in (('',1,False), ('a'*32,True,False),
                ('a'*32,-1,False), ('a'*32,1,'false')):
            with self.subTest(identifier=identifier, sequence=sequence, closing=closing), self.assertRaises(ValueError):
                self.presence.pulse(identifier, sequence, closing)

    def test_an_older_tab_keeps_resources_until_its_browser_polling_expires(self):
        self.presence.legacy_pulse()
        self.presence.pulse(self.first, 1, True)
        self.tick(60)
        self.release.assert_not_called()
        self.presence.legacy_pulse()
        self.tick(299)
        self.release.assert_not_called()
        self.tick(1); self.tick(5)
        self.release.assert_called_once()

    def test_stream_disconnect_detects_a_closed_tab_even_without_its_final_post(self):
        token = self.presence.pulse(self.first, 1)
        with self.assertRaises(ValueError): self.presence.open_watch(self.first, 'wrong')
        connection = self.presence.open_watch(self.first, token)
        for _ in range(8):
            self.tick(60)
            self.assertTrue(self.presence.watch_alive(self.first, connection))
        self.release.assert_not_called()
        self.presence.close_watch(self.first, connection)
        self.tick(0); self.tick(5)
        self.release.assert_called_once()

    def test_reconnected_stream_is_not_closed_by_its_predecessor(self):
        token = self.presence.pulse(self.first, 1)
        old = self.presence.open_watch(self.first, token)
        new = self.presence.open_watch(self.first, token)
        self.presence.close_watch(self.first, old)
        self.assertTrue(self.presence.watch_alive(self.first, new))
        self.tick(30)
        self.release.assert_not_called()

    def test_expired_stream_nonce_requires_an_authenticated_heartbeat_to_renew(self):
        token = self.presence.pulse(self.first, 1)
        self.now += 300
        with self.assertRaises(ValueError): self.presence.open_watch(self.first, token)
        self.presence.pulse(self.first, 2)
        self.assertIsNotNone(self.presence.open_watch(self.first, token))
