import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from run import OUT, ROOT, WORK, PY, run

services = WORK / 'services'
packages = sorted(services.glob('*.deb'))
assert len(packages) == 5
for package in packages:
    subprocess.run(['dpkg-deb','--extract',package,services/'root'],check=True)
env = {'LD_LIBRARY_PATH':str(services/'root/usr/lib/x86_64-linux-gnu')}
binary = services/'root/usr/sbin/mosquitto'
run('mqtt-binary-version',[binary,'-h'],env=env)
run('mqtt-package-identities',['sha256sum',*packages])
config = services/'mosquitto-test.conf'
config.write_text('listener 58983 127.0.0.1\nallow_anonymous true\npersistence false\n')
with socket.socket() as probe:
    probe.bind(('127.0.0.1',58983))
with (OUT/'logs/mqtt-broker.log').open('w') as log:
    proc = subprocess.Popen([str(binary),'-c',str(config),'-v'],env=dict(os.environ,**env),
                            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        deadline = time.monotonic()+10
        while True:
            assert proc.poll() is None
            try:
                with socket.create_connection(('127.0.0.1',58983),.2):
                    break
            except OSError:
                assert time.monotonic()<deadline
                time.sleep(.1)
        code = run('mqtt-live',[PY,'-m','pytest','tests_temp/mqtt/test_integration.py','-q','-ra',
                   '-p','no:cacheprovider','--junitxml',OUT/'xml/mqtt-live.xml'])
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
print('test-only broker stopped, exit=',proc.returncode)
raise SystemExit(code)
