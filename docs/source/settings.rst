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

A static finder to get the assets used from ``app/assets`` and ``ASSETFILES_DIRS`` folders.

.. code-block:: python
  :emphasize-lines: 6

  # project/settings/base.py

  STATICFILES_FINDERS = [
      "django.contrib.staticfiles.finders.FileSystemFinder",
      "django.contrib.staticfiles.finders.AppDirectoriesFinder",
      "picomet.finders.AssetFinder",
  ]

Django automatically serves the static files during development under the URL `STATIC_URL <https://docs.djangoproject.com/en/5.0/ref/settings/#std-setting-STATIC_URL>`_.
