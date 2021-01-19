# Copyright 2017 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Mycroft skill to pair a device to the Selene backend."""
import time
from requests import HTTPError
from threading import Timer, Lock
from uuid import uuid4

from adapt.intent import IntentBuilder

import mycroft.audio
from mycroft.api import DeviceApi, is_paired, check_remote_pairing
from mycroft.identity import IdentityManager
from mycroft.messagebus.message import Message
from mycroft.skills.core import MycroftSkill, intent_handler


PLATFORMS_WITH_BUTTON = ('mycroft_mark_1', 'mycroft_mark_2')
TWENTY_HOURS = 72000
MAX_PAIRING_CODE_RETRIES = 30


def _stop_speaking():
    """Stop speaking the pairing code if it is still being spoken."""
    if mycroft.audio.is_speaking():
        mycroft.audio.stop_speaking()


class PairingSkill(MycroftSkill):

    poll_frequency = 10  # secs between checking server for activation

    def __init__(self):
        super(PairingSkill, self).__init__("PairingSkill")
        self.api = DeviceApi()
        self.data = None
        self.time_code_expires = None
        self.state = str(uuid4())
        self.activator = None
        self.activator_lock = Lock()
        self.activator_cancelled = False
        self.platform = None

        self.counter_lock = Lock()
        self.count = -1  # for repeating pairing code. -1 = not running

        self.nato_alphabet = None

        self.mycroft_ready = False
        self.pair_dialog_lock = Lock()
        self.paired_dialog = 'pairing.paired'
        self.pairing_performed = False

        self.pairing_code_retry_cnt = 0

    def initialize(self):
        self.add_event("mycroft.not.paired", self.not_paired)
        self.nato_alphabet = self.translate_namedvalues('codes')
        self.platform = self.config_core['enclosure'].get('platform', 'unknown')
        self._select_paired_dialog()

        # If the device isn't paired catch mycroft.ready to report
        # that the device is ready for use.
        # This assumes that the pairing skill is loaded as a priority skill
        # before the rest of the skills are loaded.
        if not is_paired():
            self.add_event("mycroft.ready", self.handle_mycroft_ready)

    def _select_paired_dialog(self):
        """Select the correct dialog file to communicate pairing complete."""
        if self.platform in PLATFORMS_WITH_BUTTON:
            self.paired_dialog = 'pairing.paired'
        else:
            self.paired_dialog = 'pairing.paired.no.button'

    def handle_mycroft_ready(self, _):
        """Catch info that skills are loaded and ready."""
        with self.pair_dialog_lock:
            if is_paired() and self.pairing_performed:
                self.speak_dialog(self.paired_dialog)
            else:
                self.mycroft_ready = True

    def not_paired(self, message):
        if not message.data.get('quiet', True):
            self.speak_dialog("pairing.not.paired")
        self.handle_pairing()

    @intent_handler(IntentBuilder("PairingIntent")
                    .require("PairingKeyword").require("DeviceKeyword"))
    def handle_pairing(self, message=None):
        """Attempt to pair the device to the Selene database."""
        if check_remote_pairing(ignore_errors=True):
            # Already paired! Just tell user
            self.speak_dialog("already.paired")
        elif self.data is None:
            pairing_started = self._check_pairing_in_process()
            if not pairing_started:
                self.reload_skill = False  # Prevent restart during the process
                self.log.info("Initiating pairing sequence...")
                self._execute_pairing_sequence()

    def _check_pairing_in_process(self):
        """Determine if skill was invoked while pairing is in process."""
        pairing_started = False
        with self.counter_lock:
            if self.count > -1:
                # We snuck in to this handler somehow while the pairing
                # process is still being setup.  Ignore it.
                self.log.debug("Ignoring call to handle_pairing")
                pairing_started = True
            # Not paired or already pairing, so start the process.
            self.count = 0

        return pairing_started

    def _execute_pairing_sequence(self):
        """Interact with the user to pair the device."""
        self._get_pairing_data()
        if self.data is not None:
            self._communicate_create_account_url()
            self._communicate_pairing_url()

            if not self.activator:
                self._create_activator()

    def _get_pairing_data(self):
        """Obtain a pairing code and access token from the Selene API

        A pairing code is good for 20 hours so set an expiration time in case
        pairing does not complete.  If the call to the API fails, retry for
        five minutes.  If the API call does not succeed after five minutes
        abort the pairing process.
        """
        self.log.info('Retrieving pairing code from device API...')
        try:
            self.data = self.api.get_code(self.state)
            self.pairing_code = self.data['code']
            self.api_access_token = self.data['token']
        except Exception:
            self.log.exception("API call to retrieve pairing data failed")
            time.sleep(10)
            if self.pairing_code_retry_cnt < MAX_PAIRING_CODE_RETRIES:
                self.pairing_code_retry_cnt += 1
                self.abort_and_restart(quiet=True)
            else:
                self.end_pairing('connection.error')
                self.pairing_code_retry_cnt = 0
        else:
            self.log.info('Pairing code obtained')
            self.pairing_code_expiration = time.monotonic() + TWENTY_HOURS
            self.pairing_code_retry_cnt = 0  # Reset counter on success

    def _communicate_create_account_url(self):
        """Tell the user the URL for creating an account and display it."""
        if self.gui.connected:
            self.log.info("Communicating account URL to user")
            self.gui['show_pair_button'] = False
            self.gui.show_page("create_account.qml", override_idle=True)
            self.speak_dialog("create.account")
            mycroft.audio.wait_while_speaking()
            self.gui['show_pair_button'] = True
            msg = self.bus.wait_for_message('pairing_skill.account_created', 20.0)
            if msg is None:
                self.log.info('Timed out waiting for account created event')
            else:
                self.log.info('Account created event received')

    def _communicate_pairing_url(self):
        """Tell the user the URL for pairing and display it, if possible"""
        self.log.info("Communicating pairing URL to user")
        mycroft.audio.wait_while_speaking()
        self.gui.show_page("pairing_start.qml", override_idle=True)

        self.speak_dialog("pairing.intro")

        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text("mycroft.ai/pair      ")
        # HACK this gives the Mark 1 time to scroll the address and
        # the user time to browse to the website.
        # TODO: mouth_text() really should take an optional parameter
        # to not scroll a second time.
        time.sleep(7)
        mycroft.audio.wait_while_speaking()

    def _create_activator(self):
        """Set a timer to check the activation status in ten seconds."""
        with self.activator_lock:
            if not self.activator_cancelled:
                self.activator = Timer(
                    self.poll_frequency, self.check_for_activate
                )
                self.activator.daemon = True
                self.activator.start()

    def check_for_activate(self):
        """Method is called every 10 seconds by Timer. Checks if user has
        activated the device yet on account.mycroft.ai and if not repeats
        the pairing code every 60 seconds.
        """
        try:
            # Attempt to activate.  If the user has completed pairing on the,
            # backend, this will succeed.  Otherwise it throws and HTTPError()
            token = self.data.get("token")
            login = self.api.activate(self.state, token)  # HTTPError() thrown
        except HTTPError:
            self._check_speak_code_interval()
            self._check_pairing_code_expired()
        except Exception:
            self.log.exception("An unexpected error occurred.")
            self.abort_and_restart()
        else:
            self._save_identity(login)
            self._handle_pairing_success()

    def _save_identity(self, login):
        """Save this device's identifying information to disk.

        The user has successfully paired the device on account.mycroft.ai.
        The UUID and access token of the device can now be saved to the
        local identity file.  If saving the identity file fails twice,
        something went very wrong and the pairing process will restart.
        """
        save_attempts = 1
        while save_attempts < 2:
            try:
                IdentityManager.save(login)
            except Exception:
                if save_attempts == 1:
                    save_attempts += 1
                    log_msg = "First attempt to save identity file failed."
                    self.log.exception(log_msg)
                    time.sleep(2)
                else:
                    log_msg = (
                        "Second attempt to save identity file failed. "
                        "Restarting the pairing sequence..."
                    )
                    self.log.exception(log_msg)
                    self.abort_and_restart()
            else:
                self.log.info('Identity file saved.')
                break

    def _handle_pairing_success(self):
        """Steps to take after successful device activation."""
        _stop_speaking()
        self._display_pairing_success()
        self.bus.emit(Message("mycroft.paired", login))
        self.pairing_performed = True
        self._speak_pairing_success()
        self._cleanup_after_pairing()

    def _display_pairing_success(self):
        """Display a pairing complete screen on GUI or clear Arduino"""
        if self.gui.connected:
            self.gui.show_page("pairing_done.qml", override_idle=False)
        else:
            self.enclosure.activate_mouth_events()  # clears the display

    def _speak_pairing_success(self):
        """Tell the user the device is paired.

        If the device is not ready for use, also tell the user to wait until
        the device is ready.
        """
        with self.pair_dialog_lock:
            if self.mycroft_ready:
                # Tell user they are now paired
                self.speak_dialog(self.paired_dialog)
                mycroft.audio.wait_while_speaking()
            else:
                self.speak_dialog("wait.for.startup")
                mycroft.audio.wait_while_speaking()

    def _cleanup_after_pairing(self):
        # Un-mute.  Would have been muted during onboarding for a new
        # unit, and not dangerous to do if pairing was started
        # independently.
        self.bus.emit(Message("mycroft.mic.unmute", None))

        # Send signal to update configuration
        self.bus.emit(Message("configuration.updated"))

        # Allow this skill to auto-update again
        self.reload_skill = True

    def _check_pairing_code_expired(self):
        """The pairing code expires after 20 hours; get new code if expired."""
        if time.monotonic() > self.pairing_code_expiration:
            # After 20 hours the token times out.  Restart
            # the pairing process.
            with self.counter_lock:
                self.count = -1
            self.data = None
            self.handle_pairing()
        else:
            # trigger another check in 10 seconds
            self._create_activator()

    def _check_speak_code_interval(self):
        """Only speak pairing code every 60 seconds."""
        with self.counter_lock:
            if self.count == 0:
                self.speak_code()
            self.count = (self.count + 1) % 6

    def speak_code(self):
        """Speak pairing code."""
        code = self.data.get("code")
        self.log.info("Pairing code: " + code)
        data = {"code": '. '.join(map(self.nato_alphabet.get, code)) + '.'}

        # Make sure code stays on display
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(self.data.get("code"))
        self.gui['code'] = self.data.get("code")
        self.gui.show_page("pairing.qml", override_idle=True)
        self.speak_dialog("pairing.code", data)

    def end_pairing(self, error_dialog):
        """Resets the pairing and don't restart it.

        Arguments:
            error_dialog: Reason for the ending of the pairing process.
        """
        self.speak_dialog(error_dialog)
        self.bus.emit(Message("mycroft.mic.unmute", None))

        self.data = None
        self.count = -1

    def abort_and_restart(self, quiet=False):
        # restart pairing sequence
        self.log.debug("Aborting Pairing")
        self.enclosure.activate_mouth_events()
        if not quiet:
            self.speak_dialog("unexpected.error.restarting")

        # Reset state variables for a new pairing session
        with self.counter_lock:
            self.count = -1
        self.activator = None
        self.data = None  # Clear pairing code info
        self.log.info("Restarting pairing process")
        self.bus.emit(Message("mycroft.not.paired",
                              data={'quiet': quiet}))

    def shutdown(self):
        with self.activator_lock:
            self.activator_cancelled = True
            if self.activator:
                self.activator.cancel()
        if self.activator:
            self.activator.join()


def create_skill():
    return PairingSkill()
