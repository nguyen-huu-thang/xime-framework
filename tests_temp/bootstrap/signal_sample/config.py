from xime.adapters.socket import configure_socket_controllers
from xime.adapters.web.routing import configure_controllers
from xime.core.config import BindingConfig

dependency = BindingConfig()
dependency.scan('tests_temp.bootstrap.signal_sample.api')
configure_controllers('tests_temp.bootstrap.signal_sample.api')
configure_socket_controllers('tests_temp.bootstrap.signal_sample.api')
