from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_doc_orientation_classify=False, # 通过 use_doc_orientation_classify 参数指定不使用文档方向分类模型
    use_doc_unwarping=False, # 通过 use_doc_unwarping 参数指定不使用文本图像矫正模型
    use_textline_orientation=False, # 通过 use_textline_orientation 参数指定不使用文本行方向分类模型
)

result = ocr.predict(r"C:\Users\Administrator\Desktop\wechat_2025-08-15_155754_146.png")

text = ''
for res in result:
    res_json = res.json
    text_json = res_json.get('res')
    all_text = text_json.get('rec_texts')
    for i in all_text:
        text += i

print(text)


