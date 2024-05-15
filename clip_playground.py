from sentence_transformers import SentenceTransformer, util
from flask import Flask, request, jsonify
from PIL import Image
import io

img_model = SentenceTransformer('sentence-transformers/clip-ViT-L-14')
app = Flask('CLIP API')


@app.route('/upload_image', methods=['POST'])
def upload_image():
    image_file = request.files['image']
    data = image_file.read()
    img = Image.open(io.BytesIO(data))
    response = {
        'embed': img_model.encode(img).tolist()
    }
    return jsonify(response)


@app.route('/process_text', methods=['POST'])
def process_text():
    text = request.json['text']
    response = {
        'embed': img_model.encode(text).tolist()
    }
    return jsonify(response)


app.run(host='localhost', port=5656)
