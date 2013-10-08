# Licensed to Tomaz Muraus under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# Tomaz muraus licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import with_statement

import os
import subprocess
import time
import socket
import atexit

__all__ = [
    'TCPProcessRunner'
]


class TCPProcessRunner(object):
    """
    Represents a long running process which exposes a TCP interface
    and should be running during the test execution.
    """
    def __init__(self, args, wait_for_address, wait_for_timeout=10, cwd=None,
                 log_path='process.log'):
        """
        :param args: Arguments passed to the subprocess.Popen.
        :type args: ``list``

        :param wait_for_address: IP address and port to which we will connect
                                 to, to determine if the process is running.
        :type wait_for_address: ``tuple`` (e.g. ``('127.0.0.1', 8080)``)

        :param wait_for_timeout: How long to wait (in seconds) for the process
                                 to start before giving up.
        :type wait_for_timeout: ``float``

        :param cwd: Working directory for the subprocess.Popen. (optional)
        :type cwd: ``str``

        :param log_path: Path to the log file where the process output will be
                         saved. (optional)
        :type log_path: ``str``
        """
        if not isinstance(args, (tuple, list)):
            raise ValueError('args argument must be a list or a tuple')

        if not isinstance(wait_for_address, (list, tuple)) or \
           len(wait_for_address) != 2:
            raise ValueError('wait_for_address must be a tuple with 2 '
                             'elements')

        self._args = args or []
        self._cwd = cwd or os.getcwd()
        self._wait_for_address = wait_for_address
        self._wait_for_timeout = wait_for_timeout
        self._log_path = log_path

        self._process = None

    def setUp(self, *args, **kwargs):
        """
        Start a managed process and wait for it to come online.
        """
        env = os.environ.copy()
        with open(self._log_path, 'a+') as log_fp:
            self.process = subprocess.Popen(self._args, shell=False,
                                            cwd=self._cwd, stdout=log_fp,
                                            stderr=log_fp,
                                            env=env)
            self._wait_for_running(self._wait_for_address,
                                   self._wait_for_timeout)

        atexit.register(self.tearDown)
        return self._process

    def _wait_for_running(self, address, timeout=10):
        """
        Wait for the process to come online.

        :param address: IP address and port to which we will connect
                        to, to determine if the process is running.
        :type address: ``tuple`` (e.g. ``('127.0.0.1', 8080)``)

        :param timeout: How long to wait (in seconds) for the process to start
                        before giving up.
        :type timeout: ``float``
        """
        process = self.process
        start = time.time()

        while time.time() < start + timeout:
            process.poll()

            if process.returncode:
                # Process exited early
                raise RuntimeError('Process failed to start and exited with'
                                   ' code: %s' % (process.returncode))

            try:
                s = socket.create_connection(address)
                s.close()
                break
            except:
                time.sleep(0.5)
        else:
            process.poll()

            if process and process.returncode is None:
                process.terminate()

            raise RuntimeError('Couldn\'t connect to server')

    def tearDown(self, *args, **kwargs):
        """
        Terminate the running process.

        Note: This function does not need to be called manually. Once you call
        :func:`setUp` function it automatically registers this function to run
        on the process exit.
        """
        if self.process:
            self.process.terminate()
