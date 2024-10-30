Comet
=====

The ``picomet.backends.picomet.PicometTemplates`` class implements Picomet's template backend API for Django.

Layout
------

A ``Layout`` is used by a page or a nested layout

.. code-block:: html
  :emphasize-lines: 9,10,11

  <!-- comets/Base.html -->
  <!doctype html>
  <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    </head>
    <body>
      <main>
        <Outlet />
      </main>
    </body>
  </html>

.. code-block:: text
  :emphasize-lines: 2,9

  <!-- apps/core/comets/pages/About.html -->
  <Layout @="Base">
    <Helmet>
      <title>About</title>
    </Helmet>
    <section>
      <h1>This is the about page</h1>
    </section>
  </Layout>

.. warning::
  Everything outside of ``Layout`` tag will be ignored.


Variable
--------

To embed any data into a template, use the ``{$ $}`` syntax or ``s-text`` attribute.

.. code-block:: html

  <span>{$ request.method $}</span>
  or
  <span s-text="request.method"></span>

Expression in ``s-text`` and ``{$ $}`` is evaluated using the python's built in ``eval`` function.


DTL
---

If the comet syntax is not enough for you, Picomet provides ``Django Template Language``'s two features in comet template.

Variable
~~~~~~~~

You can use ``DTL``'s double curly braces syntax if you want to use any filter.

.. code-block:: django

  <div>
    {{ request.method|lower }}
  </div>

Tag
~~~

You can use single ``DTL`` tags inside comet templates.

.. code-block:: django

  <div>
    {% url 'core:index' %}
  </div>


.. warning::
  Comet template doesn't support multi tags like ``{% comment %}{% endcomment %}``


.. _targets:

Targets
-------

``Targets`` is a list of strings, sent as a request header which picomet uses to partially render a page.

.. _s-group:

s-group
~~~~~~~

Picomet uses the ``s-group`` attribute to partially render parts of a page on the server.

See how to use ``s-group`` in the :doc:`/action` guide.

s-param
~~~~~~~

When you navigate from ``/&bookmarksPage=1`` to ``/&bookmarksPage=2``, Picomet partially renders ``s-param="bookmarksPage"`` elements in that page.


Navigation
----------

For navigation Picomet provides a custom Alpine.js directive named ``x-link``

.. code-block:: html

  <div>
    <a href="/about" x-link>About</a>
  </div>

When navigating from a page to another page, picomet partially renders ``s-group="page"`` elements in that template on the server and returns a json of those partials.


Form
----

For submitting forms, Picomet provides a custom Alpine.js directive named ``x-form``

When the form is submitted, only the form element is partially rendered on the server.

.. code-block:: html

  <!-- apps/core/comets/Login.html -->
  <form method="post" x-form>
    {% csrf_token %}
    <input type="text" name="username" s-bind:value="form['username'].value() or ''" />
    <input type="password" name="password" s-bind:value="form['password'].value() or ''" />
    <button type="submit">Login</button>
  </form>

.. code-block:: python

  # apps/core/views.py
  from django.contrib.auth import authenticate, login
  from django.contrib.auth.forms import AuthenticationForm
  from django.http import HttpRequest
  from picomet.decorators import template
  from picomet.views import render

  @template("Login")
  def login(request: HttpRequest):
    context = {}
    form = AuthenticationForm(request.user)
    if request.method == "POST" and not request.action:
        form = AuthenticationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
    context["form"] = form
    return render(request, context)


Head
----

Put content inside the ``head`` tag from outside.

Helmet
~~~~~~

Put ``title`` and ``meta`` tags inside the ``head`` tag

.. code-block:: text

  <!-- apps/core/comets/Home.html -->
  <Layout @="Base">
    <Helmet>
      <title>Home</title>
      <meta name="title" content="..." />
      <meta name="description" content="..." />
    </Helmet>
    <section>
      Home page
    </section>
  </Layout>

.. warning::
  Tags supported inside the ``Helmet`` tag are ``title`` and ``meta``.

.. _group:

Group
~~~~~

Define a place for a group of :ref:`Css <css>` or :ref:`Scss <scss>` files

.. code-block:: html

  <head>
    ...
    <Group name="styles" />
    ...
  </head>


Assets
------

.. _css:

Css
~~~

.. code-block:: css

  /* apps/core/comets/Page.css or apps/core/assets/Page.css */
  div a {
    color: red;
  }

Load it in a :ref:`Group <group>`

.. code-block:: text
  :emphasize-lines: 2

  <!-- apps/core/comets/Page.html -->
  <Css @="Page.css" group="styles" />
  <div>
   <a>Link</a>
  </div>

.. _scss:

Sass
~~~~

.. code-block:: scss

  // apps/core/comets/Page.scss or apps/core/assets/Page.scss
  div {
    a {
      color: red;
    }
  }

Load it in a :ref:`Group <group>`

.. code-block:: text
  :emphasize-lines: 2

  <!-- apps/core/comets/Page.html -->
  <Sass @="Page.scss" group="styles" />
  <div>
   <a>Link</a>
  </div>

.. important::
  ``Sass`` requires `sass <https://npmjs.com/package/sass>`_  and `javascript <https://pypi.org/project/javascript/>`_. Run ``npm i sass`` and ``pip install javascript``

Js
~~~

.. code-block:: javascript

  /* apps/core/comets/Page.js or apps/core/assets/Page.js */
  export say(value){
    alert(value);
  }

.. code-block:: text
  :emphasize-lines: 2

  <!-- apps/core/comets/Page.html -->
  <Js @="Page.js" />
  <button @click="say('hello')">say hello</button>

Ts
~~~

.. code-block:: typescript

  // apps/core/comets/Page.ts or apps/core/assets/Page.ts
  export say(value: string){
    alert(value);
  }

.. code-block:: text
  :emphasize-lines: 2

  <!-- apps/core/comets/Page.html -->
  <Ts @="Page.ts" />
  <button @click="say('hello')">say hello</button>

.. important::
  ``Ts`` requires `esbuild <https://npmjs.com/package/esbuild>`_  and `javascript <https://pypi.org/project/javascript/>`_. Run ``npm i esbuild`` and ``pip install javascript``

s-asset:
~~~~~~~~

Import any asset from ``app/assets`` or :ref:`ASSETFILES_DIRS <assetfiles_dirs>`

.. code-block:: html

  <img s-asset:src="images/icon.png" />


Directive
---------

s-context
~~~~~~~~~

Set a context for a block

.. code-block:: html

  <div s-context="core.get_message">
    <span>{$ message $}</span>
  </div>

.. code-block:: python

  # apps/core/contexts.py

  def get_message(context):
      return {
        "message": f"hi, {context['user'].username}",
      }

s-bind:
~~~~~~~

Bind data to an attribute

.. code-block:: html

  <a s-bind:href="blog.slug" x-link>{$ blog.title $}</a>

s-toggle:
~~~~~~~~~

Toggle boolean attribute

.. code-block:: html

  <button s-toggle:disabled="not user.is_authenticated"></button>

s-static:
~~~~~~~~~

Import any static file from ``app/static`` or ``STATICFILES_DIRS``

.. code-block:: html

  <link rel="stylesheet" s-static:href="styles/main.css" />


Component
---------

Defining a component

.. code-block:: text

  <!-- apps/core/comets/Counter.html -->
  <div x-data={count: 0}>
    <button @click="count++">+</button>
    <span x-text="count"></span>
    <button @click="count--">-</button>
  </div>

Using the component

.. code-block:: text

  <Include @="Counter" />
  or
  <Import.Counter @="Counter" />
  <Counter />

Children
~~~~~~~~

Defining a component with children

.. code-block:: html

  <!-- apps/core/comets/Card.html -->
  <div class="card">
    <Children />
  </div>

Using the component

.. code-block:: text

  <Include @="Card">
    card body
  </Include>
  or
  <Import.Card @="Card" />
  <Card>
    card body
  </Card>


Default
~~~~~~~

Setting default context props in a component

.. code-block:: html

  <!-- apps/core/comets/ProductItem.html -->
  <Default show_add="True">
    <div s-if="show_add">
      add to cart
    </div>
  </Default>

Using the component

.. code-block:: text

  <Include @="ProductItem" /> <!-- show_add is True -->
  or
  <Include @="ProductItem" .show_add="False" /> <!-- show_add is False -->

.. note::
  Use dot(.) prefix to provide a context variable to a component.

s-props
~~~~~~~

Pass normal attributes to a component

.. code-block:: html

  <!-- apps/core/comets/Component.html -->
  <button s-props>click</button>

.. code-block:: text

  <Include @="Component" class="text-red-500" />


Condition
---------

.. code-block:: html

  <div s-if="user.is_superuser">
    hi admin
  </div>
  <div s-elif="user.is_authenticated">
    hi user
  </div>
  <div s-else>
    please login
  </div>

.. code-block:: html

  <div s-show="user.is_superuser" s-group="auth">
    hi admin
  </div>


Loop
----

.. code-block:: html

  <div s-for="blog" s-in="blogs">
    <div>
      {$ blog.title $}
    </div>
  </div>
  <div s-empty>
    No blogs found
  </div>

Since django ORM querysets are lazy, we can fetch a single item from the database and render it on server then update it on client.

To partially update a single item or something in that item, picomet requires ``s-of``, ``s-key`` and ``s-keys`` attributes.

See how to use ``s-of``, ``s-key`` and ``s-keys`` in the :doc:`/action` guide.


Fragment
--------

Wrap multiple elements in a single conditional block.

.. code-block:: html

  <Fragment s-if="user.is_superuser">
    <h2>hi</h2>,
    <span>{$ user.username $}</span>
  </Fragment>


With
----

Pass a variable to a part of template

.. code-block:: html

  <With username="user.username">
    {$ username $}
  </With>


Debug
-----

Contents inside the ``Debug`` tag will only be parsed when ``Debug=True`` in ``settings``.

.. code-block:: text

  <Debug>
    <Js @="picomet/hmr.js" />
  </Debug>


Pro
---

Contents inside the ``Pro`` tag will only be parsed when ``Debug=False`` in ``settings``.

.. code-block:: text

  <Pro>
    <Js @="analytics.js" />
  </Pro>


Tailwind
--------

.. code-block:: text
  :emphasize-lines: 6

  <!-- comets/Base.html -->
  <!doctype html>
  <html lang="en">
    <head>
      ...
      <Tailwind @="base" />
      ...
    </head>
    <body>
      ...
    </body>
  </html>

.. warning::
  The ``Tailwind`` tag must be inside the head tag.

.. important::
  ``Tailwind`` requires `tailwindcss <https://npmjs.com/package/tailwindcss>`_ and `javascript <https://pypi.org/project/javascript/>`_. Run ``npm i tailwindcss`` and ``pip install javascript``

.. note::
  To minify the css on production, just do ``npm i cssnano``

For tailwind to work, picomet requires 3 files.

.. code-block:: css

  /* comets/base.tailwind.css */
  @tailwind base;
  @tailwind components;
  @tailwind utilities;

.. code-block:: javascript

  /** comets/base.tailwind.js */
  /** @type {import('tailwindcss').Config} */
  module.exports = {
    theme: {},
    plugins: [],
  };

.. code-block:: javascript

  /** comets/base.postcss.js */
  const tailwindcss = require("tailwindcss");

  module.exports = {
    plugins: [tailwindcss],
  };


Comet.js
--------

The ``picomet/comet.js`` module provides comet templates it's client side routing and partial updating capabilities.

It also provides some utility functions to help you update your pages.

go
~~~

Use this function to navigate to a page

.. code-block:: typescript

  go(path: string, scrollToTop?: boolean): Promise<void>

.. list-table::
   :header-rows: 1

   * - Parameter
     - Default
     - Description
   * - path: string
     -
     - Path to navigate to
   * - scrollToTop?: boolean
     - false
     - Whether to scroll to the top of the page

update
~~~~~~

Use this function to partially update a page

.. code-block:: typescript

  update(
    targets: string[],
    url?: string,
    scrollToTop?: boolean
  ): Promise<void>

.. list-table::
   :header-rows: 1

   * - Parameter
     - Default
     - Description
   * - targets: string[]
     -
     - Targets list
   * - url?: string
     - location.toString()
     - Url to navigate to
   * - scrollToTop?: boolean
     - false
     - Whether to scroll to the top of the page

call
~~~~

Use this function to call an action

Learn more about ``call`` and ``actions`` in the :doc:`/action` guide.


Alpine SSR
----------

The cool thing about picomet is it's ability to render alpine.js on the server

.. note::
  Alpine.js directives supported on the server are ``x-data``, ``x-show``, ``x-text``, ``x-bind``. Learn more about these on `alpinejs.dev <https://alpinejs.dev>`_

.. important::
  To render Alpine.js syntax on the server Picomet requires `py-mini-racer <https://pypi.org/project/py-mini-racer>`_. Run ``pip install py-mini-racer``

s-prop
~~~~~~

To pass any data from the server context dictionary to the javascript context, use the s-prop directive.

.. code-block:: python

  # apps/core/views.py
  from picomet.decorators import template
  from picomet.views import render

  @template("Page")
  def page(request):
      context = {"variable": "hello world"}
      return render(request, context)

.. code-block:: html

  <!-- apps/core/comets/Page.html -->
  <div s-prop:_var="variable" x-data="{var: _var}" server>
    <span x-text="var"></span>
  </div>

.. important::
  The ``server`` attribute is required to know if the alpine directives inside a block should be rendered on the server. The ``client`` attribute can be used inside a ``server`` block to exclude a block from being rendered on the server.

isServer
~~~~~~~~

Check if alpine is being rendered on server or client.

.. code-block:: html

  <div x-show="isServer">
    <span>visible on server</span>
  </div>
  <div x-show="!isServer">
    <span>visible on client</span>
  </div>


Builtins
--------

Picomet provides some helpful builtins to use inside templates.

safe
~~~~

Mark a string as safe for use in HTML.

.. code-block:: html

  <div>
    <span>{$ safe(blog.content) $}</span>
    or
    <span s-text="safe(blog.content)"></span>
  </div>

csrf_token
~~~~~~~~~~

Get the CSRF input.

.. code-block:: django

  <form>
    {% csrf_token %}
  </form>

csrf_input
~~~~~~~~~~

Get the CSRF input value.

.. code-block:: html

  <form>
    <input type="hidden" name="csrf_token" s-bind:value="csrf_input()" />
  </form>
