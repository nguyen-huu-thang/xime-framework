from xime.core.config import BindingConfig

dependency = BindingConfig()
dependency.scan("sample_app.api")
dependency.scan("sample_app.refdata")
