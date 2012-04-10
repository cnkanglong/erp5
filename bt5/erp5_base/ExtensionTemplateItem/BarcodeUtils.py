def generateBarcodeImage(self, barcode_type, data):
  # huBarcode's DataMatrix support has limitation for data size.
  # huBarcode's QRCode support is broken.
  # more 1-D barcode types can be added by pyBarcode library.
  barcode_type = barcode_type.lower()
  if barcode_type == 'datamatrix':
    from subprocess import Popen, PIPE
    process = Popen(['dmtxwrite'],
                     stdin=PIPE,
                     stdout=PIPE,
                     stderr=PIPE,
                     close_fds=True)
    output, error = process.communicate(input=data)
  elif barcode_type == 'ean13':
    from hubarcode.ean13 import EAN13Encoder 
    encoder = EAN13Encoder(data)
    output = encoder.get_imagedata()
  elif barcode_type == 'code128':
    from hubarcode.code128 import Code128Encoder 
    encoder = Code128Encoder(data)
    output = encoder.get_imagedata()
  elif barcode_type == 'qrcode':
    import qrcode
    from cStringIO import StringIO
    fp = StringIO()
    img = qrcode.make(data)
    img.save(fp, format='png')
    fp.seek(0)
    output = fp.read()
  else:
    raise NotImplementedError, 'barcode_type=%s is not supported' % barcode_type
  RESPONSE = self.REQUEST.RESPONSE
  RESPONSE.setHeader('Content-Type', 'image/png')
  RESPONSE.setHeader('Content-Length', len(output))
  return output
