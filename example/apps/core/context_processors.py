def has_liked(blog, user):
    return user.is_authenticated and blog.like_set.filter(user=user).exists()


def has_bookmarked(blog, user):
    return user.is_authenticated and blog.bookmark_set.filter(user=user).exists()


def common(request):
    return {
        "has_liked": has_liked,
        "has_bookmarked": has_bookmarked,
    }
