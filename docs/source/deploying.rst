Deploying
=========

Install requirements
~~~~~~~~~~~~~~~~~~~~

Install the production requirements

.. code-block:: bash

  pip install -r requirements.txt

If using Tailwind

.. code-block:: bash

  npm ci


Compile project
~~~~~~~~~~~~~~~

Run ``python manage.py build`` to compile the project before starting the production server.


Serve assets
~~~~~~~~~~~~

Configure the production server to serve the compiled asset files inside ``.picomet/build/assets`` folder under the URL :ref:`ASSET_URL <asset_url>`.


Start server
~~~~~~~~~~~~

Now start the production server using ``wsgi`` or ``asgi``. Go to django `How to deploy Django <https://docs.djangoproject.com/en/5.0/howto/deployment/>`_ documentation to learn more.
