import copy
from functools import reduce
import operator
from typing import Union, Optional, Tuple, Iterable

from pip._vendor.packaging.markers import Marker as PackageMarker
from pip._vendor.packaging.markers import InvalidMarker
from pdm.models.specifiers import PySpecSet
from pdm.utils import join_list_with


class Marker(PackageMarker):
    def copy(self) -> "Marker":
        inst = self.__class__('os_name == "nt"')
        inst._markers = copy.deepcopy(self._markers)
        return inst

    def __and__(self, other: Optional[PackageMarker]) -> "Marker":
        if other is None:
            return self
        lhs = f"({self})" if "or" in self._markers else str(self)
        rhs = f"({other})" if "or" in other._markers else str(other)
        marker_str = f"{lhs} and {rhs}"
        return type(self)(marker_str)

    def __rand__(self, other: Optional[PackageMarker]) -> "Marker":
        if other is None:
            return self
        rhs = f"({self})" if "or" in self._markers else str(self)
        lhs = f"({other})" if "or" in other._markers else str(other)
        marker_str = f"{lhs} and {rhs}"
        return type(self)(marker_str)

    def __or__(self, other: Optional[PackageMarker]) -> "Marker":
        if other is None:
            return self
        marker_str = f"{self} or {other}"
        return type(self)(marker_str)

    def __ror__(self, other: Optional[PackageMarker]) -> "Marker":
        if other is None:
            return self
        marker_str = f"{other} or {self}"
        return type(self)(marker_str)

    def split_pyspec(self) -> Tuple[Optional["Marker"], PySpecSet]:
        """Split `python_version` and `python_full_version` from marker string"""
        if _only_contains_python_keys(self._markers):
            return None, _build_pyspec_from_marker(self._markers)
        if 'or' in self._markers:
            return self.copy(), PySpecSet()
        py_markers = [marker for marker in self._markers if marker != 'and' and _only_contains_python_keys(marker)]
        rest = [marker for marker in self._markers if marker != 'and' and marker not in py_markers]
        new_markers = join_list_with(rest, 'and')
        if not new_markers:
            marker = None
        else:
            marker = self.copy()
            marker._markers = new_markers
        return marker, _build_pyspec_from_marker(join_list_with(py_markers, 'and'))


def get_marker(marker: Union[PackageMarker, Marker, None]) -> Optional[Marker]:
    return Marker(str(marker)) if marker else None


def split_marker_element(
    text: str, element: str
) -> Tuple[Iterable[Tuple[str, str]], Optional[Marker]]:
    """An element can be stripped from the marker only if all parts are connected
    with `and` operater. The rest part are returned as a string or `None` if all are
    stripped.

    :param text: the input marker string
    :param element: the element to be stripped
    :returns: an iterable of (op, value) pairs together with the stripped part.
    """
    if not text:
        return [], text
    marker = Marker(text)
    if "or" in marker._markers:
        return [], text
    result = []
    bare_markers = [m for m in marker._markers if m != "and"]
    for m in bare_markers[:]:
        if not isinstance(m, tuple):
            continue
        if m[0].value == element:
            result.append(tuple(e.value for e in m[1:]))
            bare_markers.remove(m)
    new_markers = join_list_with(bare_markers, "and")
    if not new_markers:
        return result, None
    marker._markers = new_markers
    return result, marker


def _only_contains_python_keys(markers):
    if isinstance(markers, tuple):
        return markers[0].value in ('python_version', 'python_full_version')

    for marker in markers:
        if marker in ('and', 'or'):
            continue
        if not _only_contains_python_keys(marker):
            return False
    return True


def _build_pyspec_from_marker(markers):
    groups = [PySpecSet()]
    for marker in markers:
        if isinstance(marker, list):
            groups[-1] = groups[-1] & _build_pyspec_from_marker(marker)
        elif isinstance(marker, tuple):
            key, op, version = [i.value for i in marker]
            if key == 'python_version':
                if op == '>':
                    int_versions = [int(ver) for ver in version.split('.')]
                    int_versions += 1
                    version = '.'.join(str(v) for v in int_versions)
                    op = '>='
                elif op == '==':
                    version += '.*'
            pyspec = PySpecSet(f'{op}{version}')
            groups[-1] = groups[-1] & pyspec
        else:
            assert marker in ('and', 'or')
            if marker == 'or':
                groups.append(PySpecSet())
    return reduce(operator.or_, groups)


def join_metaset(metaset: Tuple[Optional[Marker], PySpecSet]) -> Optional[Marker]:
    marker, pyspec = metaset
    py_marker = pyspec.as_marker_string() or None
    py_marker = Marker(py_marker) if py_marker else None
    try:
        return marker & py_marker
    except TypeError:
        return None