import litserve as ls
import torch
import open_clip
from PIL import Image


class EmbeddingAPI(ls.LitAPI):
    def setup(self, device):
        self.model, _, self.preprocess = open_clip.create_model_and_transforms('ViT-B-32',
                                                                               pretrained='laion2b_s34b_b79k',
                                                                               device=device)
        self.model.eval()  # model in train mode by default
        self.tokenizer = open_clip.get_tokenizer('ViT-B-32')
    
    def predict(self, request):
        if 'image_path' in request:
            input_image = Image.open(request['image_path'])
            image = self.preprocess(input_image).unsqueeze(0)
            with torch.no_grad(), torch.autocast("cuda"):
                return self.model.encode_image(image)
        elif 'string' in request:
            input_string = request['string']
            tokens = self.tokenizer([input_string])
            with torch.no_grad(), torch.autocast("cuda"):
                return self.model.encode_text(tokens)
        else:
            raise ValueError('Invalid request')

    def encode_response(self, output):
        return {"embedding": output[0].tolist()} # return one embedding vector

if __name__ == "__main__":
    api = EmbeddingAPI(api_path='/embed')
    server = ls.LitServer(api, accelerator='cpu')
    server.run(port=8001)
