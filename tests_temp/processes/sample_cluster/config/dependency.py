from xime.core.config import BindingConfig

dependency = BindingConfig()
dependency.scan("sample_cluster.api")
dependency.scan("sample_cluster.jobs")
