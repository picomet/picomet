Settings
========

.. _asset_url:

ASSET_URL
---------

*type* : ``str``

*default* : ``"assets/"``

URL used to serve the assets like css, scss, js and others imported in your comet templates. Assets are stored inside ``app/assets`` folders.

Picomet automatically serves the compiled asset files on this URL during development. See the :doc:`/deploying` guide to learn how to serve the compiled assets on production.

.. _assetfiles_dirs:

ASSETFILES_DIRS
---------------

*type* : ``list[str|Path]``

*default* : ``[]``

Additional assets directories besides ``app/assets`` dirs.
