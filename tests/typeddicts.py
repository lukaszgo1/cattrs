"""Strategies for typed dicts."""
from datetime import datetime
from string import ascii_lowercase
from typing import Generic, List, Optional, TypedDict, TypeVar

from attr import NOTHING
from hypothesis.strategies import (
    DrawFn,
    SearchStrategy,
    booleans,
    composite,
    datetimes,
    integers,
    just,
    lists,
    sets,
    text,
)

from .untyped import gen_attr_names

# Type aliases for readability
TypedDictType = type
T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")


@composite
def int_attributes(
    draw: DrawFn, total: bool = True
) -> tuple[int, SearchStrategy, SearchStrategy]:
    if total:
        return int, integers(), text(ascii_lowercase)
    else:
        return int, integers() | just(NOTHING), text(ascii_lowercase)


def datetime_attributes(
    total: bool = True,
) -> SearchStrategy[tuple[datetime, SearchStrategy, SearchStrategy]]:
    success_strat = datetimes().map(lambda dt: dt.replace(microsecond=0))
    return just(
        (
            datetime,
            success_strat if total else success_strat | just(NOTHING),
            text(ascii_lowercase),
        )
    )


@composite
def list_of_int_attributes(
    draw: DrawFn, total: bool = True
) -> tuple[List[int], SearchStrategy, SearchStrategy]:
    if total:
        return List[int], lists(integers()), text(ascii_lowercase).map(lambda v: [v])
    else:
        return (
            List[int],
            lists(integers()) | just(NOTHING),
            text(ascii_lowercase).map(lambda v: [v]),
        )


@composite
def simple_typeddicts(
    draw: DrawFn, total: Optional[bool] = None
) -> tuple[TypedDictType, dict]:
    """Generate simple typed dicts.

    :param total: Generate the given totality dicts (default = random)
    """
    if total is None:
        total = draw(booleans())

    attrs = draw(
        lists(
            int_attributes(total)
            | list_of_int_attributes(total)
            | datetime_attributes(total)
        )
    )

    attrs_dict = {n: attr[0] for n, attr in zip(gen_attr_names(), attrs)}
    success_payload = {}
    for n, a in zip(attrs_dict, attrs):
        v = draw(a[1])
        if v is not NOTHING:
            success_payload[n] = v

    cls = TypedDict("HypTypedDict", attrs_dict, total=total)

    if draw(booleans()):

        class InheritedTypedDict(cls):
            inherited: int

        cls = InheritedTypedDict
        success_payload["inherited"] = draw(integers())

    return (cls, success_payload)


@composite
def simple_typeddicts_with_extra_keys(
    draw: DrawFn, total: Optional[bool] = None
) -> tuple[TypedDictType, dict, set[str]]:
    """Generate TypedDicts, with the instances having extra keys."""
    cls, success = draw(simple_typeddicts(total))

    # The normal attributes are 2 characters or less.
    extra_keys = draw(sets(text(ascii_lowercase, min_size=3, max_size=3)))
    success.update({k: 1 for k in extra_keys})

    return cls, success, extra_keys


@composite
def generic_typeddicts(
    draw: DrawFn, total: Optional[bool] = None
) -> tuple[TypedDictType, dict]:
    """Generate generic typed dicts.

    :param total: Generate the given totality dicts (default = random)
    """
    if total is None:
        total = draw(booleans())

    attrs = draw(
        lists(
            int_attributes(total)
            | list_of_int_attributes(total)
            | datetime_attributes(total),
            min_size=1,
        )
    )

    attrs_dict = {n: attr[0] for n, attr in zip(gen_attr_names(), attrs)}
    success_payload = {}
    for n, a in zip(attrs_dict, attrs):
        v = draw(a[1])
        if v is not NOTHING:
            success_payload[n] = v

    # We choose up to 3 attributes and make them generic.
    generic_attrs = draw(
        lists(integers(0, len(attrs) - 1), min_size=1, max_size=3, unique=True)
    )
    generics = []
    actual_types = []
    for ix, (attr_name, attr_type) in enumerate(list(attrs_dict.items())):
        if ix in generic_attrs:
            typevar = TypeVar(f"T{ix+1}")
            generics.append(typevar)
            actual_types.append(attr_type)
            attrs_dict[attr_name] = typevar

    cls = make_typeddict(
        "HypTypedDict", attrs_dict, total=total, bases=[Generic[*generics]]
    )

    if draw(booleans()):

        class InheritedTypedDict(cls):
            inherited: int

        cls = InheritedTypedDict
        success_payload["inherited"] = draw(integers())

    return (cls[*actual_types], success_payload)


def make_typeddict(
    cls_name: str, attrs: dict[str, type], total: bool = True, bases: list = []
) -> TypedDictType:
    from inspect import get_annotations

    globs = {"TypedDict": TypedDict}
    lines = []

    bases_snippet = ",".join(f"_base{ix}" for ix in range(len(bases)))
    for ix, base in enumerate(bases):
        globs[f"_base{ix}"] = base
    if bases_snippet:
        bases_snippet = f", {bases_snippet}"

    lines.append(f"class {cls_name}(TypedDict{bases_snippet},total={total}):")
    for n, t in attrs.items():
        globs[f"_{n}_type"] = t
        lines.append(f"  {n}: _{n}_type")

    script = "\n".join(lines)
    eval(compile(script, "name", "exec"), globs)

    cls = globs[cls_name]

    print(len(attrs))
    print(get_annotations(cls))
    if len(attrs) != len(get_annotations(cls)):
        breakpoint()

    return cls
