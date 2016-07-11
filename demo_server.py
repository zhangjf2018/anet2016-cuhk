"""
A minimal server for web demo of action recognition
"""
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
from pyActionRec.action_classifier import ActionClassifier
from pyActionRec.anet_db import ANetDB
import numpy as np
import youtube_dl
import urlparse

app = Flask(__name__)

# upload folder to hold uploaded/downloaded files
UPLOAD_FOLDER = 'tmp/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# model specifications
models = [('models/resnet200_anet_2016_deploy.prototxt',
           'models/resnet200_anet_2016.caffemodel',
           1.0, 0, True),
          ('models/bn_inception_anet_2016_temporal_deploy.prototxt',
           'models/bn_inception_anet_2016_temporal.caffemodel',
           0.2, 1, False)
          ]

GPU = 0

# init global variables
cls = ActionClassifier(models, dev_id=GPU)
db = ANetDB.get_db("1.3")
lb_list = db.get_ordered_label_list()

ydl = youtube_dl.YoutubeDL({u'outtmpl': u'tmp/%(id)s.%(ext)s'})


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ['avi', 'mp4', 'webm', 'mkv']


@app.route("/")
def main():
    return render_template('index.html')


def build_cls_ret(scores, k):
    idx = np.argsort(scores)[::-1]

    top_k_results = []
    for i in xrange(k):
        k = idx[i]
        top_k_results.append({
            'name': lb_list[k],
            'score': str(scores[k])
        })

    return top_k_results


def run_classification(filename):
    try:
        scores, frm_scores, total_time = cls.classify(filename)
    except:
        return jsonify(error='classification failed'), 200, {'ContentType': 'application/json'}
    finally:
        # clear the file
        print "cleaning up the file contents"
        os.remove(filename)

    ret = build_cls_ret(scores, 3)

    # return the result in json
    return jsonify(error=None, results=ret, total_time=total_time, n_snippet=len(frm_scores), fps=1), 200, {
        'ContentType': 'application/json'}


@app.route("/upload_video", methods=['POST'])
def upload_video():
    if 'video_file' not in request.files:
        return jsonify(error='upload not found'), 200, {'ContentType': 'application/json'}

    upload_file = request.files['video_file']
    if upload_file.filename == '':
        return jsonify(error='the file has no name'), 200, {'ContentType': 'application/json'}

    if upload_file and allowed_file(upload_file.filename):
        filename = secure_filename(upload_file.filename)

        # first save the file
        savename = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        upload_file.save(savename)

        # classify the video
        return run_classification(savename)

    else:
        return jsonify(error='empty or not allowed file'), 200, {'ContentType': 'application/json'}


@app.route("/upload_url", methods=['POST'])
def upload_url():
    data = request.form
    url = data['video_url']

    try:
        file_info = ydl.extract_info(unicode(url))
    except:
        return jsonify(error='invalid URL'), 200, {'ContentType': 'application/json'}

    filename = os.path.join('tmp',file_info['id']+'.'+file_info['ext'])

    # classify the video
    return run_classification(filename)

if __name__ == "__main__":
    # run the Flask app
    app.debug = True
    app.run()