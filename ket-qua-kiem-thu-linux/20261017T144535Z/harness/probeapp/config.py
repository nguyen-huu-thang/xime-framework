from xime.core.config import BindingConfig
from xime.adapters.web.routing import configure_controllers
from xime.adapters.socket import configure_socket_controllers

dependency = BindingConfig()
dependency.scan('probeapp.api')
configure_controllers('probeapp.api')
configure_socket_controllers('probeapp.api')
