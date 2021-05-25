# Django Frozen Data

Django model custom field for storing a frozen snapshot of an object.

## Principles

* Behaves _like_ a `ForeignKey` but the data is detached from the related object
* Transparent to the client - it looks and behaves like the original object
* The frozen object cannot be resaved
* Supports nesting of objects

## Usage

A frozen field can be declared like a `ForeignKey`:

```python
class Foo:
    frozen_bar = FrozenObjectField(Bar, help_text="This is a frozen snapshot of the object.")
    fresh_bar = ForeignKey(Bar, help_text="This is a live FK relationship.")
```

The field behaves exactly like a FK, with the exception that the object cannot be saved:

```python
>>> bar = Bar()
>>> foo = Foo.objects.create(frozen_bar=bar, fresh_bar=bar)
>>> # the fresh field can be updated as you would expect
>>> foo.fresh_bar.save()
>>> # the frozen field cannot - to prevent overwriting new data.
>>> foo.frozen_bar.save()
>>> StaleObjectError: 'Object was frozen; defrosted objects cannot be saved.'
```

### Issues - TODO

- [x] Deserialization of DateField/DateTimeField values
- [x] Deserialization of DecimalField values
- [x] Deserialization of UUIDField values
- [ ] Deep object freezing

#### Running tests

The tests themselves use `pytest` as the test runner. If you have installed the `poetry` evironment, you can run them thus:

```
$ poetry run pytest
```
