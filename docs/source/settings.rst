Settings
========

.. _assetfiles_dirs:

ASSETFILES_DIRS
---------------

*type* : ``list[str|Path]``

*default* : ``[]``

Additional assets directories besides ``app/assets`` dirs.


STATICFILES_FINDERS>
--------------------

A static finder to get the assets from ``app/assets`` and ``ASSETFILES_DIRS`` folders.

.. code-block:: python

  # project/settings/base.py

  STATICFILES_FINDERS = [
      ...
      "picomet.finders.AssetFinder",
  ]

Django automatically serves the static files during development under the URL `STATIC_URL <https://docs.djangoproject.com/en/5.0/ref/settings/#std-setting-STATIC_URL>`_.
