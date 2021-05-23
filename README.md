# Django Frozen Data

Django model custom field for storing a frozen snapshot of an object.

## Principles

* Behaves _like_ a `ForeignKey` but the data is detached from the related object
* Transparent to the client - it looks and behaves like the original object
* The frozen object cannot be resaved
* Supports nesting of objects

### Issues - TODO

- [ ] Deserialization of DateField/DateTimeField values
- [ ] Deserialization of DecimalField values
- [ ] Deserialization of UUIDField values

#### Running tests

The tests themselves use `pytest` as the test runner. If you have installed the `poetry` evironment, you can run them thus:

```
$ poetry run pytest
```
