# Django Frozen Data

Django model custom field for storing a frozen snapshot of an object.

## Principles

* Behaves _like_ a `ForeignKey` but the data is detached from the related object
* Transparent to the client - it looks and behaves like the original object
* The frozen object cannot be edited
* The frozen object cannot be saved
* Supports nesting of objects

## Usage

A frozen field can be declared like a `ForeignKey`:

```python
class Profile(Model):

    address = FrozenObjectField(
        Address,
        include=[],
        exclude=["line_2"],
        select_related=[],
        select_properties=[]
    )
...

>>> profile.address = Address.objects.get(...)
>>> profile.address
"29 Acacia Avenue"
>>> profile.save()
>>> type(profile.address)
Address
>>> profile.refresh_from_db()
>>> type(profile.address)
types.FrozenAddress
>>> profile.address.line_1
"29 Acacia Avenue"
>>> dataclasses.asdict(profile.address)
{
    "meta": {
        "pk": 1,
        "model": "Address",
        "frozen_at": "...",
        "fields": {
            "id": "django.db.models.AutoField",
            "line_1": "django.db.models.CharField",
            "line_2": "django.db.models.CharField"
        },
        "include": ["id", "line_1"],
        "exclude": ["line_2"],
        "select_related": []
    },
    "id": 1,
    "line_1": "29 Acacia Avenue"
}
>>> profile.address.id
1
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
flatten out the parts of the object tree that you wish to record.

That said, there is limited support for related object capture.

TBC

### Issues - TODO

- [x] Deserialization of DateField/DateTimeField values
- [x] Deserialization of DecimalField values
- [x] Deserialization of UUIDField values
- [x] Deep object freezing

#### Running tests

The tests themselves use `pytest` as the test runner. If you have installed the `poetry` evironment, you can run them thus:

```
$ poetry run pytest
```
