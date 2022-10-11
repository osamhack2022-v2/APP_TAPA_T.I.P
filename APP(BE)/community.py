from flask import Flask, render_template, Blueprint, request
import os, pyrebase, requests
import time, datetime

from mySecrets import config
from users import check_token

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()
storage = firebase.storage()

bp = Blueprint("community", __name__, url_prefix="/community")

#best 게시물 목록
@bp.route("/best/", methods=["GET"])
def get_best_list():
  pass

#new 게시물 목록
@bp.route("/new/", methods=["GET"])
def get_new_list():
  return db.child("posts").order_by_child("updated_at").get().val(), 200

#자유게시판 게시물 목록
@bp.route("/posts/", methods=["GET"])
def get_post_list():
  return db.child("posts").get().val(), 200

#게시물 상세 내용 + comments
@bp.route("/posts/<post_id>", methods=["GET"])
def get_specific_post(post_id):
  post = db.child("posts").child(post_id).get().val()
  comments = db.child("comments").order_by_child("post_id").equal_to(post_id).get().val()
  if comments == []:
    comments = {}
  return {"post": post, "comments": comments}, 200

#게시물 좋아요 / 좋아요 삭제 
@bp.route("/posts/<post_id>/like", methods=["POST"])
def like_this_post(post_id):
  token = request.headers.get("Authorization") 
  decoded = check_token(token)
  if decoded == "invalid token":
    return {"status": "Invalid token, requires login again"}, 403
  
  user_id = decoded["localId"]
  
  like = db.child("users").child(user_id).child("likes").child(post_id).get().val()
  if like is None:
    db.child("users").child(user_id).child("likes").child(post_id).set(1)
    db.child("posts").child(post_id).child("likes").child(user_id).set(1)
  else: 
    db.child("users").child(user_id).child("likes").child(post_id).remove()
    db.child("posts").child(post_id).child("likes").child(user_id).remove()
  return {"status": "like success"}, 200

#게시물 작성, login required.
@bp.route("/posts/", methods=["POST"])
def post_a_post():
  token = request.headers.get("Authorization") 
  decoded = check_token(token)
  if decoded == "invalid token":
    return {"status": "Invalid token, requires login again"}, 403

  #fields 
  user_id = decoded["localId"]

  params = request.get_json()
  u_title = params["title"]
  u_content = params["content"]
  u_tags = params["tags"]

  CUR_TIME = int(time.time())
  u_created_at = CUR_TIME
  u_updated_at = CUR_TIME

  res = db.child("posts").push({
    "user_id": user_id,
    "title": u_title,
    "content": u_content,
    "tags": u_tags,
    "created_at": u_created_at,
    "updated_at": u_updated_at,
    "likes": 0,
    "views": 0
  })

  #print(res)
  db.child("users").child(user_id).child("posts").update({
    res["name"]: u_created_at
  })

  return {"status": "post success", "post_id": res["name"]}, 200

#게시물 수정, login required. 
@bp.route("/posts/<post_id>", methods=["PUT"])
def update_post(post_id):
  token = request.headers.get("Authorization") 
  decoded = check_token(token)
  if decoded == "invalid token":
    return {"status": "Invalid token, requires login again"}, 403

  #fields 
  user_id = decoded["localId"]
  try:
    post_user_id = db.child("posts").child(post_id).get().val()["user_id"]
  except:
    return {"status": "Post ID is wrong"}, 403

  if (user_id != post_user_id):
    return {"status": "Not owner of post"}, 403

  params = request.get_json()
  u_title = params["title"]
  u_content = params["content"]
  u_tags = params["tags"]

  CUR_TIME = int(time.time())
  u_updated_at = CUR_TIME

  res = db.child("posts").child(post_id).update({
    "title": u_title,
    "content": u_content,
    "tags": u_tags,
    "updated_at": u_updated_at,
  })

  return {"status": "put success"}, 200

#게시물 삭제, login required. 
@bp.route("/posts/<post_id>", methods=["DELETE"])
def delete_post(post_id):
  token = request.headers.get("Authorization") 
  decoded = check_token(token)
  if decoded == "invalid token":
    return {"status": "Invalid token, requires login again"}, 403

  #fields 
  user_id = decoded["localId"]
  try:
    post_user_id = db.child("posts").child(post_id).get().val()["user_id"]
  except:
    return {"status": "Post ID is wrong"}, 403

  if (user_id != post_user_id):
    return {"status": "Not owner of post"}, 403

  db.child("posts").child(post_id).remove()
  db.child("users").child(user_id).child("posts").child(post_id).remove()
  return {"status": "delete success"}, 200

#댓글 작성, login required.
@bp.route("/comment/<post_id>", methods=["POST"])
def post_a_comment(post_id):
  token = request.headers.get("Authorization") 
  decoded = check_token(token)
  if decoded == "invalid token":
    return {"status": "Invalid token, requires login again"}, 403
  #print(decoded)

  #fields 
  user_id = decoded["localId"]

  params = request.get_json()
  u_content = params["content"]

  CUR_TIME = int(time.time())
  u_created_at = CUR_TIME

  res = db.child("comments").push({
    "post_id": post_id,
    "user_id": user_id,
    "content": u_content,
    "created_at": u_created_at,
    "likes": 0,
  })

  db.child("posts").child(post_id).child("comments").update({
    res["name"]: u_created_at
  })

  db.child("users").child(user_id).child("comments").update({
    res["name"]: u_created_at
  })

  return {"status": "comment post success", "comment_id": res["name"]}, 200


#댓글 삭제, login required.
@bp.route("/comment/<comment_id>", methods=["DELETE"])
def delete_comment(comment_id):
  token = request.headers.get("Authorization") 
  decoded = check_token(token)
  if decoded == "invalid token":
    return {"status": "Invalid token, requires login again"}, 403

  #fields 
  user_id = decoded["localId"]
  try:
    comment =  db.child("comments").child(comment_id).get().val()
    c_user_id = comment["user_id"]
    c_post_id = comment["post_id"]
  except:
    return {"status": "Comment ID is wrong"}, 403

  if (user_id != c_user_id):
    return {"status": "Not owner of post"}, 403

  db.child("comments").child(comment_id).remove()
  db.child("users").child(user_id).child("comments").child(comment_id).remove()
  db.child("posts").child(c_post_id).child("comments").child(comment_id).remove()
  return {"status": "delete success"}, 200