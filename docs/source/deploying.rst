Deploying
=========

Serving assets
~~~~~~~~~~~~~~

- Run ``python manage.py build`` to compile assets before starting the production server.
- Configure the production server to serve the compiled asset files inside ``.picomet/build/assets`` folder under the URL :ref:`ASSET_URL <asset_url>`.

Go to django `How to deploy Django <https://docs.djangoproject.com/en/5.0/howto/deployment/>`_ documentation to learn about deploying.
