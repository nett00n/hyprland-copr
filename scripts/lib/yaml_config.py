"""Centralized ruamel.yaml configuration."""

import io
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

_NO_WRAP_WIDTH = 10_000_000_000


class YamlConfig:
    """Configurable YAML serialization with sensible defaults."""

    def __init__(
        self,
        indent: int = 2,
        explicit_start: bool = False,
        width: int = _NO_WRAP_WIDTH,
        offset: int = 0,
    ):
        """Initialize YAML serializer config.

        Args:
            indent: Indentation level (mapping and sequence both)
            explicit_start: Add --- document marker
            width: Line width (large number = no wrapping)
            offset: Sequence item offset (0 = dash at parent indent)
        """
        self.indent = indent
        self.explicit_start = explicit_start
        self.width = width
        self.offset = offset

    def _make_yaml(self) -> YAML:
        """Create configured YAML instance."""
        yml = YAML()
        yml.default_flow_style = False
        yml.allow_unicode = True
        yml.width = self.width
        yml.indent(mapping=self.indent, sequence=self.indent, offset=self.offset)
        yml.explicit_start = self.explicit_start
        return yml

    @staticmethod
    def _wrap_literals(obj):
        """Recursively mark multiline strings for literal block style."""
        if isinstance(obj, str) and "\n" in obj:
            return LiteralScalarString(obj)
        if isinstance(obj, dict):
            return {k: YamlConfig._wrap_literals(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [YamlConfig._wrap_literals(v) for v in obj]
        return obj

    def dump(self, data: dict) -> str:
        """Serialize data to YAML string with configured style."""
        yml = self._make_yaml()
        buf = io.StringIO()
        yml.dump(self._wrap_literals(data), buf)
        return buf.getvalue()


# Default config: yamllint-compliant (2-space, no sequence offset, no sorting)
DEFAULT = YamlConfig(indent=2, explicit_start=False, width=_NO_WRAP_WIDTH, offset=0)


def FORMAT_FILE(indent: int, explicit_start: bool) -> YamlConfig:
    """Create YAML config for file formatting with detected indentation."""
    return YamlConfig(
        indent=indent, explicit_start=explicit_start, width=_NO_WRAP_WIDTH, offset=0
    )
