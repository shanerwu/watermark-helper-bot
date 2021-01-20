import configparser
import tempfile, os

from flask import Flask, request, abort
from PIL import Image, ImageDraw, ImageFont
from imgurpython import ImgurClient

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageMessage, ImageSendMessage
)

app = Flask(__name__)

config = configparser.ConfigParser()
config.read("config_local.ini")

line_bot_api = LineBotApi(config['line_bot_token']['channel_access_token'])
handler = WebhookHandler(config['line_bot_token']['channel_secret'])


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=(ImageMessage, TextMessage))
def handle_image(event):
    if isinstance(event.message, ImageMessage):
        ext = 'jpg'
        message_content = line_bot_api.get_message_content(event.message.id)
        with tempfile.NamedTemporaryFile(prefix=ext+'-', delete=False) as tf:
            for chunk in message_content.iter_content():
                tf.write(chunk)
            tempfile_path = tf.name
        dist_path = tempfile_path + '.' + ext
        os.rename(tempfile_path, dist_path)
        try:
            add_watermark('版權所有，請勿外流', 'NotoSansTC-Regular.otf', dist_path)

            clinet_id = config['imgur_token']['client_id']
            client_secret = config['imgur_token']['client_secret']
            access_token = config['imgur_token']['access_token']
            refresh_token = config['imgur_token']['refresh_token']

            client = ImgurClient(clinet_id ,client_secret ,access_token ,refresh_token)
            upload = client.upload_from_path(dist_path, config=None, anon=False)
            
            os.remove(dist_path)

            image_message = ImageSendMessage(
                original_content_url = upload['link'],
                preview_image_url = upload['link']
            )
            line_bot_api.reply_message(
                event.reply_token,
                image_message
            )
        except:
            os.remove(dist_path)

            line_bot_api.reply_message(
            event.reply_token, [
                TextSendMessage(text='error')
            ])


def add_watermark(text, font_name, image_file):
    original_image = Image.open(image_file)
    original_image_size = original_image.size
    original_image_width = original_image_size[0]
    original_image_height = original_image_size[1]
    
    font_size = 1
    image_fraction = 0.30
    font = ImageFont.truetype(font_name, font_size)
    while font.getsize(text)[0] < image_fraction * original_image_width:
        # iterate until the text size is just larger than the criteria (fraction * image geometric mean)
        font_size += 1
        font = ImageFont.truetype(font_name, font_size)

    # calculate text size in pixels (width, height)
    text_size = font.getsize(text) 
    # create image for text
    text_image = Image.new('RGBA', text_size, (255, 255, 255, 0))
    text_draw = ImageDraw.Draw(text_image)

    # draw text on image
    text_draw.text((0, 0), text, (220, 220, 220, 129), font=font)
    
    # rotate text image and fill with transparent color
    rotated_text_image = text_image.rotate(45, expand=True, fillcolor=(0, 0, 0, 0))
    rotated_text_image_size = rotated_text_image.size

    # calculate top/left corner for centered text
    parts = 8
    offset_x = original_image_width//parts
    offset_y = original_image_height//parts

    start_x = original_image_width//parts - rotated_text_image_size[0]//2
    start_y = original_image_height//parts - rotated_text_image_size[1]//2

    combined_image = original_image.convert('RGBA')
    for a in range(0, parts, 2):
        for b in range(0, parts, 2):
            x = start_x + a*offset_x
            y = start_y + b*offset_y
            # image with the same size and transparent color (..., ..., ..., 0)
            watermarks_image = Image.new('RGBA', original_image_size, (255, 255, 255, 0))
            # put text in expected place on watermarks image
            watermarks_image.paste(rotated_text_image, (x, y))
            # put watermarks image on original image
            combined_image = Image.alpha_composite(combined_image, watermarks_image)

    combined_image = combined_image.convert("RGB")
    combined_image.save(image_file)


if __name__ == "__main__":
    app.run()
