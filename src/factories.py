#!/usr/bin/env python3
"""Factory utilities for dynamic class loading from configuration."""

import importlib
from typing import Any, Dict

from src.utils.logger_setup import logger, log_exception


def create_instance_from_config(config: Dict[str, Any], **kwargs: Any) -> Any:
    """Create an instance of a configured class.

    Args:
        config: Mapping with ``module_path`` and ``class_name`` keys.
        **kwargs: Runtime constructor arguments.

    Returns:
        Created class instance.
    """
    module_path = config.get("module_path")
    class_name = config.get("class_name")

    if not module_path or not class_name:
        raise ValueError(f"Configuration missing 'module_path' or 'class_name': {config}")

    try:
        logger.info(f"Loading implementation: {module_path}.{class_name}")
        module = importlib.import_module(module_path)
        klass = getattr(module, class_name)
        return klass(**kwargs)
    except (ImportError, AttributeError) as error:
        log_exception(f"Failed to load class '{class_name}' from '{module_path}'.")
        raise ImportError(f"Не удалось импортировать {class_name} из {module_path}") from error
    except Exception:
        log_exception(f"Unexpected error while creating class '{class_name}'.")
        raise
