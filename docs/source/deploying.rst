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

To compile for production, run

.. code-block:: bash

  python manage.py build


Collect statics
~~~~~~~~~~~~~~~

Collect asset files and static files in the `STATIC_ROOT <https://docs.djangoproject.com/en/stable/ref/settings/#std-setting-STATIC_ROOT>`_ folder

.. code-block:: bash

  python manage.py collectstatic


Serve statics
~~~~~~~~~~~~~

Configure the production server to serve the collected files inside `STATIC_URL <https://docs.djangoproject.com/en/stable/ref/settings/#std-setting-STATIC_URL>`_ folder under the URL ``STATIC_URL``.

See `How to deploy static files <https://docs.djangoproject.com/en/stable/howto/static-files/deployment/>`_ guide to learn more.


Start server
~~~~~~~~~~~~

Now start the production server using ``wsgi`` or ``asgi``. Go to django `How to deploy Django <https://docs.djangoproject.com/en/5.0/howto/deployment/>`_ documentation to learn more.
