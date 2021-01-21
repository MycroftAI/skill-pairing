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


ACTION_BUTTON_PLATFORMS = ('mycroft_mark_1', 'mycroft_mark_2')
MAX_PAIRING_CODE_RETRIES = 30
ACTIVATION_POLL_FREQUENCY = 10  # secs between checking server for activation


def _stop_speaking():
    """Stop speaking the pairing code if it is still being spoken."""
    if mycroft.audio.is_speaking():
        mycroft.audio.stop_speaking()


class PairingSkill(MycroftSkill):
    """Device pairing logic."""
    def __init__(self):
        super(PairingSkill, self).__init__("PairingSkill")
        self.api = DeviceApi()
        self.pairing_token = None
        self.pairing_code = None
        self.pairing_code_expiration = None
        self.state = str(uuid4())
        self.platform = None
        self.nato_alphabet = None
        self.counter_lock = Lock()
        self.mycroft_ready = False
        self.pairing_code_retry_cnt = 0
        self.account_creation_requested = False

        # These attributes track the status of the device activation
        self.device_activation_lock = Lock()
        self.device_activation_checker = None
        self.device_activation_cancelled = False
        self.activation_attempt_count = 0

        # These attributes are used when tracking the ready state to control
        # when the paired dialog is spoken.
        self.paired_dialog_lock = Lock()
        self.paired_dialog = None
        self.pairing_performed = False

        # These attributes are used when determining if pairing has started.
        self.pairing_status_lock = Lock()
        self.pairing_in_progress = False

    def initialize(self):
        """Stuff to do after constructor but before intent."""
        self.add_event("mycroft.not.paired", self.not_paired)
        self.nato_alphabet = self.translate_namedvalues('codes')
        # TODO replace self.platform logic with call to enclosure capabilities
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
        if self.platform in ACTION_BUTTON_PLATFORMS:
            self.paired_dialog = 'pairing.paired'
        else:
            self.paired_dialog = 'pairing.paired.no.button'

    def handle_mycroft_ready(self, _):
        """Catch info that skills are loaded and ready."""
        with self.paired_dialog_lock:
            if is_paired() and self.pairing_performed:
                self.speak_dialog(self.paired_dialog)
            else:
                self.mycroft_ready = True

    def not_paired(self, message):
        """When not paired, tell the user so and start pairing."""
        if not message.data.get('quiet', True):
            self.speak_dialog("pairing.not.paired")
        self.handle_pairing()

    @intent_handler(IntentBuilder("PairingIntent")
                    .require("PairingKeyword").require("DeviceKeyword"))
    def handle_pairing(self, message=None):
        """Attempt to pair the device to the Selene database."""
        already_paired = check_remote_pairing(ignore_errors=True)
        if already_paired:
            self.speak_dialog("already.paired")
            self.log.info("Pairing skill invoked but device is paired, exiting")
        elif self.pairing_code is None:
            start_pairing = self._check_pairing_in_progress()
            if start_pairing:
                self.reload_skill = False  # Prevent restart during pairing
                self.enclosure.deactivate_mouth_events()
                self._communicate_create_account_url()
                self._execute_pairing_sequence()

    def _check_pairing_in_progress(self):
        """Determine if skill was invoked while pairing is in progress."""
        with self.pairing_status_lock:
            if self.pairing_in_progress:
                self.log.debug(
                    "Pairing in progress; ignoring call to handle_pairing"
                )
                start_pairing = False
            else:
                self.pairing_in_progress = True
                start_pairing = True

        return start_pairing

    def _communicate_create_account_url(self):
        """Tell the user the URL for creating an account and display it.

        This should only happen once per pairing sequence.  If pairing is
        restarted due to an error, this will be skipped.
        """
        if not self.account_creation_requested:
            self.log.info("Communicating account URL to user")
            self.account_creation_requested = True
            if self.gui.connected:
                self.gui.show_page("create_account.qml", override_idle=True)
            else:
                self.enclosure.mouth_text("account.mycroft.ai      ")
            self.speak_dialog("create.account")
            mycroft.audio.wait_while_speaking()
            time.sleep(30)

    def _execute_pairing_sequence(self):
        """Interact with the user to pair the device."""
        self.log.info("Initiating device pairing sequence...")
        self._get_pairing_data()
        if self.pairing_code is not None:
            self._communicate_pairing_url()
            self._display_pairing_code()
            self._speak_pairing_code()
            self._attempt_activation()

    def _get_pairing_data(self):
        """Obtain a pairing code and access token from the Selene API

        A pairing code is good for 24 hours so set an expiration time in case
        pairing does not complete.  If the call to the API fails, retry for
        five minutes.  If the API call does not succeed after five minutes
        abort the pairing process.
        """
        self.log.info('Retrieving pairing code from device API...')
        try:
            pairing_data = self.api.get_code(self.state)
            self.pairing_code = pairing_data['code']
            self.pairing_token = pairing_data['token']
            self.pairing_code_expiration = (
                    time.monotonic()
                    + pairing_data['expiration']
            )
        except Exception:
            self.log.exception("API call to retrieve pairing data failed")
            self._handle_pairing_data_retrieval_error()
        else:
            self.log.info('Pairing code obtained: ' + self.pairing_code)
            self.pairing_code_retry_cnt = 0  # Reset counter on success

    def _handle_pairing_data_retrieval_error(self):
        """Retry retrieving pairing code for five minutes, then abort."""
        if self.pairing_code_retry_cnt < MAX_PAIRING_CODE_RETRIES:
            time.sleep(10)
            self.pairing_code_retry_cnt += 1
            self.restart_pairing(quiet=True)
        else:
            self.end_pairing('connection.error')
            self.pairing_code_retry_cnt = 0

    def _communicate_pairing_url(self):
        """Tell the user the URL for pairing and display it, if possible"""
        self.log.info("Communicating pairing URL to user")
        if self.gui.connected:
            self.gui.show_page("pairing_start.qml", override_idle=True)
        else:
            self.enclosure.mouth_text("mycroft.ai/pair      ")
        self.speak_dialog("pairing.intro")
        mycroft.audio.wait_while_speaking()
        time.sleep(30)

    def _display_pairing_code(self):
        """Show the pairing code on the display, if one is available"""
        if self.gui.connected:
            self.gui['code'] = self.pairing_code
            self.gui.show_page("pairing_code.qml", override_idle=True)
        else:
            self.enclosure.mouth_text(self.pairing_code)

    def _attempt_activation(self):
        """Speak the pairing code if two """
        with self.device_activation_lock:
            if not self.device_activation_cancelled:
                self._check_speak_code_interval()
                self._start_device_activation_checker()

    def _check_speak_code_interval(self):
        """Only speak pairing code every two minutes."""
        self.activation_attempt_count += 1
        if not self.activation_attempt_count % 12:
            self._speak_pairing_code()

    def _speak_pairing_code(self):
        """Speak pairing code."""
        self.log.debug("Speaking pairing code")
        pairing_code_utterance = map(self.nato_alphabet.get, self.pairing_code)
        speak_data = dict(code='. '.join(pairing_code_utterance) + '.')
        self.speak_dialog("pairing.code", speak_data)

    def _start_device_activation_checker(self):
        """Set a timer to check the activation status in ten seconds."""
        self.device_activation_checker = Timer(
            ACTIVATION_POLL_FREQUENCY, self.check_for_device_activation
        )
        self.device_activation_checker.daemon = True
        self.device_activation_checker.start()

    def check_for_device_activation(self):
        """Call the device API to determine if user completed activation.

        Called every 10 seconds by a Timer. Checks if user has activated the
        device on account.mycroft.ai.  Activation is considered successful when
        the API call returns without error. When the API call throws an
        HTTPError, the assumption is that the uer has not yet completed
        activation.
        """
        self.log.debug('Checking for device activation')
        try:
            login = self.api.activate(self.state, self.pairing_token)
        except HTTPError:
            self._handle_not_yet_activated()
        except Exception:
            self.log.exception("An unexpected error occurred.")
            self.restart_pairing()
        else:
            self._handle_activation(login)

    def _handle_not_yet_activated(self):
        """Activation has not been completed, determine what to do next.

        The pairing code expires after 24 hours. Restart pairing if expired.
        If the pairing code is still valid, speak the pairing code if the
        appropriate amount of time has elapsed since last spoken and restart
        the device activation checking timer.
        """
        if time.monotonic() > self.pairing_code_expiration:
            self._reset_pairing_attributes()
            self.handle_pairing()
        else:
            self._attempt_activation()

    def _handle_activation(self, login):
        """Steps to take after successful device activation."""
        self._save_identity(login)
        _stop_speaking()
        self._display_pairing_success()
        self.bus.emit(Message("mycroft.paired", login))
        self.pairing_performed = True
        self._speak_pairing_success()
        self.bus.emit(Message("configuration.updated"))
        self.reload_skill = True

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
                    self.restart_pairing()
            else:
                self.log.info('Identity file saved.')
                break

    def _display_pairing_success(self):
        """Display a pairing complete screen on GUI or clear Arduino"""
        if self.gui.connected:
            self.gui.show_page("pairing_success.qml", override_idle=True)
            time.sleep(3)
            self.gui.show_page("pairing_done.qml", override_idle=False)
        else:
            self.enclosure.activate_mouth_events()  # clears the display

    def _speak_pairing_success(self):
        """Tell the user the device is paired.

        If the device is not ready for use, also tell the user to wait until
        the device is ready.
        """
        with self.paired_dialog_lock:
            if self.mycroft_ready:
                self.speak_dialog(self.paired_dialog)
                mycroft.audio.wait_while_speaking()
            else:
                self.speak_dialog("wait.for.startup")
                mycroft.audio.wait_while_speaking()

    def end_pairing(self, error_dialog):
        """Resets the pairing and don't restart it.

        Arguments:
            error_dialog: Reason for the ending of the pairing process.
        """
        self.speak_dialog(error_dialog)
        self.bus.emit(Message("mycroft.mic.unmute", None))
        self._reset_pairing_attributes()

    def restart_pairing(self, quiet=False):
        """Resets the pairing and don't restart it.

        Arguments:
            quiet: indicates if an error message should be spoken to the user
        """
        self.log.info("Aborting pairing process and restarting...")
        self.enclosure.activate_mouth_events()
        if not quiet:
            self.speak_dialog("unexpected.error.restarting")
        self._reset_pairing_attributes()
        self.bus.emit(Message("mycroft.not.paired", data=dict(quiet=quiet)))

    def _reset_pairing_attributes(self):
        """Reset attributes that need to be in a certain state for pairing."""
        with self.pairing_status_lock:
            self.pairing_in_progress = False
        with self.device_activation_lock:
            self.activation_attempt_count = 0
        self.device_activation_checker = None
        self.pairing_code = None
        self.pairing_token = None

    def shutdown(self):
        """Skill process termination steps."""
        with self.device_activation_lock:
            self.device_activation_cancelled = True
            if self.device_activation_checker:
                self.device_activation_checker.cancel()
        if self.device_activation_checker:
            self.device_activation_checker.join()


def create_skill():
    """Entrypoint for skill process to load the skill."""
    return PairingSkill()
