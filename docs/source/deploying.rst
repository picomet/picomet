Deploying
=========


Install uv
~~~~~~~~~~

.. code-block:: bash

  pip install uv

Install dependencies
~~~~~~~~~~~~~~~~~~~~

Install the production dependencies

.. code-block:: bash

  uv export --frozen > requirements.txt
  uv pip install -r requirements.txt

If using Tailwind, TypeScript or Sass etc.

.. code-block:: bash

  npm ci


Compile project
~~~~~~~~~~~~~~~

To compile for production, run

.. code-block:: bash

  export NODE_PATH=$(pwd)/node_modules
  python manage.py build


Collect statics
~~~~~~~~~~~~~~~

Collect asset files and static files in the `STATIC_ROOT <https://docs.djangoproject.com/en/stable/ref/settings/#std-setting-STATIC_ROOT>`_ folder

.. code-block:: bash

  python manage.py collectstatic


Serve statics
~~~~~~~~~~~~~

Configure the production server to serve the collected static files in the `STATIC_ROOT <https://docs.djangoproject.com/en/stable/ref/settings/#std-setting-STATIC_ROOT>`_ folder under the `STATIC_URL <https://docs.djangoproject.com/en/stable/ref/settings/#std-setting-STATIC_URL>`_.

See `How to deploy static files <https://docs.djangoproject.com/en/stable/howto/static-files/deployment/>`_ guide to learn more.

Or you can use `WhiteNoise <https://whitenoise.readthedocs.io/en/stable/>`_ to automatically serve static files.


Start server
~~~~~~~~~~~~

Now start the production server using ``wsgi`` or ``asgi``. Go to django `How to deploy Django <https://docs.djangoproject.com/en/5.0/howto/deployment/>`_ documentation to learn more.
