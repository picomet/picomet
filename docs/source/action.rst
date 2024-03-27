Action
======

An ``action`` is a server function which is called from the client using the ``call`` function, it takes a HttpRequest object as an argument and returns a :ref:`Targets <targets>` list. Picomet uses that ``Target`` list to partially render a page and return a json of those partials.

First of all, lets create a ``Blog`` and a ``Like`` model:

.. code-block:: python

  # apps/core/models.py
  from django.db import models

  class Blog(models.Model):
      title = models.CharField(max_length=150)
      content = models.TextField()
      created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

  class Like(models.Model):
      blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
      created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.blog.title

Migrate the models:

.. code-block:: shell

  python manage.py makemigrations
  python manage.py migrate

Now enter into the django shell and create a blog:

.. code-block:: shell

  python manage.py shell

.. code-block:: python

  from core.models import Blog

.. code-block:: python

  Blog.objects.create(title="First blog", content="This is the content")

Define a like action:

.. code-block:: python

  # apps/core/actions.py
  from core.models import Blog, Like

  def like_blog(request):
      blog = Blog.objects.get(id=request.POST["blog"])
      Like.objects.create(blog=blog)
      return ["&likes"]

Create a Template and ``call`` the action from the client:

.. code-block:: text

  <!-- apps/core/comets/Blogs.html -->
  <Layout @="Base">
    <div s-for="blog" s-in="blogs">
      <div>
        <h2>{$ blog.title $}</h2>
        <p>{$ blog.content $}</p>
        <span s-group="likes">likes ({$ blog.like_set.count() $})</span>
        <button
          s-bind:x-prop:blogId="blog.id"
          @click="call('core.like_blog', {blog: blogId})"
        >
          like
        </button>
      </div>
    </div>
  </Layout>

Create the view:

.. code-block:: python

  # apps/core/views.py
  from picomet.decorators import template
  from picomet.views import render
  from core.models import Blog

  @template("Blogs")
  def blogs(request):
      context = {"blogs": Blog.objects.all()}
      return render(request, context)

Configure url:

.. code-block:: python
  :emphasize-lines: 9

  # apps/core/urls.py
  from django.urls import path

  from core import views

  app_name = "core"

  urlpatterns = [
      path("blogs", views.blogs, name="blogs"),
  ]
