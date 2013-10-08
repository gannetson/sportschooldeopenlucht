from apps.wallposts.views import WallPostDetail
from django.conf.urls import patterns, url
from surlex.dj import surl
from .views import ReactionList, ReactionDetail, WallPostList

urlpatterns = patterns('',
    url(r'^$', WallPostList.as_view(), name='wallpost-list'),
    surl(r'^<pk:#>$', WallPostDetail.as_view(), name='wallpost-detail'),
    url(r'^reactions/$', ReactionList.as_view(), name='wallpost-reaction-list'),
    surl(r'^reactions/<pk:#>$', ReactionDetail.as_view(), name='wallpost-reaction-detail'),
)
