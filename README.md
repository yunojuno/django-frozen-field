# Django Frozen Field

Django model custom field for storing a frozen snapshot of an object.

## Principles

* Behaves like a `ForeignKey` but the data is detached from the related object
* Transparent to the client - it looks like the original object
* The frozen object cannot be edited
* The frozen object cannot be saved
* Works even if original model is updated or deleted

### Why not use DRF / Django serializers?

This library has one specific requirement that makes using the existing
solutions hard - to be able to decouple the frozen data from the model, such
that it can be altered or even deleted, and the data can still be used. We use
the model itself once, when we first save the data - from that point on the
field has no dependency on the original model, using intermediate dynamic
dataclasses that represent the model as it was when the data was saved. This
package does reference a lot of the principles in both DRF and Django itself -
and the structure of the serialized data is similar to that exported from the
queryset serializer.

### Why not just store frozen data as JSON and be done with it?

This is probably a good / safe option for most codebases coming to the freezing
of data for the first time, and we have a lot of ephemeral data stored in
`JSONField` fields ourselves. However, migrating an existing project from
`ForeignKey` to `JSONField`, along with all references to the data, templates,
etc., is painful. This package is designed to make the migration from 'fresh' to
'frozen' as simple as possible.

## Package internals

The package includes three core modules, `serializers`, `models`, and `fields`,
that together control the serialization process.

#### `frozen_field.models`

This module contains the engine of the package, which is a `FrozenObjectMeta`
dataclass that is responsible for parsing Django model attributes, extracting
data and and creating the dynamic dataclasses used to represent a Django Model.

You should not need to use this module in your application.

#### `frozen_field.serializers`

This module contains the `freeze_object` and `unfreeze_object` functions that
are responsible for marshalling the serialized data between a Django Model
instance, a dynamic dataclass, and the serialized JSON..

On first save:

    model >> dataclass >> dict

On first refresh:

    dict >> dataclass

On subsequent saves:

    dataclass >> dict

You should not need to use this module in your application.

#### `frozen_field.fields`

This module contains the `FrozenObjectField` itself - it is the only part of the
package that should need to use yourself.

#### Evolution of `FrozenObjectField`

The easiest way to understand why the field is structured as it is is to follow
the history:

1. The first implementation serialized just non-related object fields (i.e.
   excluded `ForeignKey` and `OneToOneField` attrs)
1. The `include` and `exclude` arguments were added to control which fields were
   serialized
1. The `select_related` argument was added to enable the serialization of
   top-level related objects (`ForeignKey` / `OneToOneField`)
1. The `select_properties` argument was added to enable the serialization of
   simple model properties (`@property`)
1. Support was added for ORM-style paths (using the `__` delimiter) to enable
   deep serialization beyond the top-level
1. The `converters` argument was added to enable fine-tuning of the
   deserialization process.

## Usage

A frozen field can be declared like a `ForeignKey`:

```python
class Profile(Model):

    address = FrozenObjectField(
        Address,                         # The model being frozen
        include=[],                      # defaults to all
        exclude=["line_2"],              # defaults to none
        select_related=[]                # add related fields
        select_properties=["attr_name"]  # add model properties
        converters={"field_name": func}  # custom deserializer
    )

...

>>> profile.address = Address.objects.get(...)
>>> profile.address
"29 Acacia Avenue"
>>> profile.save()
>>> type(profile.address)
Address
# When fetched from the db, the property becomes a frozen instance
>>> profile.refresh_from_db()
>>> type(profile.address)
types.FrozenAddress
>>> profile.address.id
1
>>> profile.address.line_1
"29 Acacia Avenue"
>>> profile.address.since
datetime.date(2011, 6, 4)
>>> dataclasses.asdict(profile.address)
{
    "_meta": {
        "pk": 1,
        "model": "Address",
        "frozen_at": "2021-06-04T18:10:30.549Z",
        "fields": {
            "id": "django.db.models.AutoField",
            "line_1": "django.db.models.CharField",
            "since": "django.db.models.DateField"
        },
        "properties": ["attr_name"]
    },
    "id": 1,
    "line_1": "29 Acacia Avenue",
    "since": "2011-06-04T18:10:30.549Z"
    "attr_name": "hello"
}
>>> profile.address.json_data()
{
    "id": 1,
    "line_1": "29 Acacia Avenue",
    "since": "2011-06-04T18:10:30.549Z",
    "attr_name": "hello"
}
>>> profile.address.id = 2
FrozenInstanceError: cannot assign to field 'id'
>>> profile.address.save()
AttributeError: 'FrozenAddress' object has no attribute 'save'
```

### Controlling serialization

By default only top-level attributes of an object are frozen - related objects
(`ForeignKey`, `OneToOneField`) are ignored. This is by design - as deep
serialization of recursive relationships can get very complex very quickly, and
a deep serialization of an object tree is not recommended. This library is
designed for the simple 'freezing' of basic data. The recommended pattern is to
flatten out the parts of the object tree that you wish to record. You can
control which top-level fields are included in the frozen data using the
`include` and `exclude` arguments. Note that these are mutually exclusive - by
default both are an empty list, which results in all top-level non-related
attributes being serialized. If `included` is not empty, then *only* the fields
in the list are serialized. If `excluded` is not empty then all fields *except*
those in the list are serialized.

That said, there is support for related object capture using the
`select_related` argument.

The `select_properties` argument can be used to add model properties (e.g.
methods decorated with `@property`) to the serialization. NB this currently does
no casting of the value when deserialized (as it doesn't know what the type is),
so if your property is a date, it will come back as a string (isoformat). If you
want it to return a `date` you will want to use converters.

The `converters` argument is used to override the default conversion of the JSON
back to something more appropriate. A typical use case would be the casting of a
property which has no default backing field to use. In this case you could use
the builtin Django `parse_date` function

```python
field = FrozenObjectField(
    Profile,
    include=[],
    exclude=[],
    select_related=[],
    select_properties=["date_registered"],
    converters={"date_registered": parse_date}
)
```

## How it works

The internal wrangling of a Django model to a JSON string is done using dynamic
dataclasses, created on the fly using the `dataclasses.make_dataclass` function.
The new dataclass contains one fixed property, `meta`, which is itself an
instance of a concrete dataclass, `FrozenObjectMeta`. This ensures that each
serialized blob contains enought original model field metadata to be able to
deserialize the JSONField back into something that resembles the original. This
is required because the process of serializing the data as JSON will convert
certain unsupported datatypes (e.g. `Decimal`, `float`, `date`, `datetime`,
`UUID`) to string equivalents, and in order to deserialize these values we need
to know what type the original value was. This is very similar to how Django's
own `django.core.serializers` work.

#### Running tests

The tests use `pytest` as the test runner. If you have installed the `poetry`
evironment, you can run them using:

```
$ poetry run pytest
```
