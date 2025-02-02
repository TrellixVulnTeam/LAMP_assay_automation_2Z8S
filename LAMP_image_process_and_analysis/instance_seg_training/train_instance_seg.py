# -*- coding: utf-8 -*-
# Formerly named "working_pytorch_instance_imseg_ccrop.py"

import os
import numpy as np
import torch
import torchvision
import torch.utils.data
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from git.repo.base import Repo
import shutil

# Update this path to the folder with images and masks
dir_in = input('Provide the root path to the image and mask.\nNote for Windows, use \'\\\'\
 as the separator and put \'\' around the path.\n')

mask_dir = input('Provide name of folder with masks.\nThey should\
 be cropped before this process.\n If they require cropping, use the \'image prep\' app.\n\
 For Windows, use \'\\\'\
 as the separator and put \'\' around the input.\n')

imag_dir = input('Provide name of folder with images.\nThey should\
 be cropped before this process.\n If they require cropping, use the \'image_prep\' app.\n\
 For Windows, use \'\\\'\
 as the separator and put \'\' around the input.\n')


class sensor_image(torch.utils.data.Dataset):
    def __init__(self, root, transforms=None, target_transform=None):
        self.root = root
        self.transforms = transforms
        self.target_transform = target_transform
        # load all image files, sorting them to
        # ensure that they are aligned
        self.imgs = list(sorted(os.listdir(os.path.join(root, imag_dir))))
        self.masks = list(sorted(os.listdir(os.path.join(root, mask_dir))))
        
    def __getitem__(self, idx):
        # load images ad masks
        img_path = os.path.join(self.root, imag_dir, self.imgs[idx])
        mask_path = os.path.join(self.root, mask_dir, self.masks[idx])
        img = Image.open(img_path).convert("RGB")
        # note that we haven't converted the mask to RGB,
        # because each color corresponds to a different instance
        # with 0 being background
        mask = Image.open(mask_path)
        
        # Convert from image object to array
        mask = np.array(mask)
        
        obj_ids = np.unique(mask)
        # first is background, other values are noise, removed them
        obj_ids = obj_ids[-4:]
        #print("objid", obj_ids)
        
        # split the color-encoded mask into a set
        # of binary masks
        masks = mask == obj_ids[:, None, None]
        #print("masks", masks)
        
        # get bounding box coordinates for each mask
        num_objs = len(obj_ids)
        boxes = []
        for i in range(num_objs):
            pos = np.where(masks[i])
            xmin = np.min(pos[1])
            xmax = np.max(pos[1])
            ymin = np.min(pos[0])
            ymax = np.max(pos[0])
            boxes.append([xmin, ymin, xmax, ymax])
         
        boxes = torch.as_tensor(boxes, dtype=torch.float32)
        #print("boxes", boxes)
        # there is only one class
        labels = torch.ones((num_objs,), dtype=torch.int64)
        #print("labels", labels)
        masks = torch.as_tensor(masks, dtype=torch.uint8)
        #print("masks", masks)
        
        image_id = torch.tensor([idx])
        #print("image_id", image_id)
        area = (boxes[:, 3] - boxes[:, 1]) * (boxes[:, 2] - boxes[:, 0])
        # suppose all instances are not crowd
        iscrowd = torch.zeros((num_objs,), dtype=torch.int64)
         
        target = {}
        target["boxes"] = boxes
        target["labels"] = labels
        target["masks"] = masks
        target["image_id"] = image_id
        target["area"] = area
        target["iscrowd"] = iscrowd
         
        if self.transforms is not None:
            img, target = self.transforms(img, target)
        
        return img, target
        
    def __len__(self):
        return len(self.imgs)


if os.path.isdir("vision") == True:
    print("vision present")
else:
    repo = Repo.clone_from("https://github.com/pytorch/vision.git", "vision", no_checkout=True)
    repo.git.checkout("2f40a483d")

shutil.copy('vision/references/detection/utils.py', 'utils.py')
shutil.copy('vision/references/detection/transforms.py', 'transforms.py')
shutil.copy('vision/references/detection/coco_eval.py', 'coco_eval.py')
shutil.copy('vision/references/detection/engine.py', 'engine.py')
shutil.copy('vision/references/detection/coco_utils.py', 'coco_utils.py')

from engine import train_one_epoch, evaluate
import utils
import transforms as oldT
# This next line is for newer versions of PyTorch and should replace oldT.
# It doesn't work currently with the rest of the code as the code is currently
# designed. This will have to be revised soon.
#import torchvision.transforms as vtransforms 

def get_transform(train):
    transforms = []
    # converts the image, a PIL image, into a PyTorch Tensor
    transforms.append(oldT.ToTensor())
    if train:
        # during training, randomly flip the training images
        # and ground-truth for data augmentation
        transforms.append(oldT.RandomHorizontalFlip(0.5))
    return oldT.Compose(transforms)


from torchvision.models.detection.mask_rcnn import MaskRCNNPredictor
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

num_classes = 5


def get_instance_segmentation_model(num_classes):
    # load an instance segmentation model pre-trained on COCO
    model = torchvision.models.detection.maskrcnn_resnet50_fpn(weights=True)
    
    # get the number of input features for the classifier
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    # replace the pre-trained head with a new one
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    
    # now get the number of input features for the mask classifier
    in_features_mask = model.roi_heads.mask_predictor.conv5_mask.in_channels
    hidden_layer = 256
    # and replace the mask predictor with a new one
    model.roi_heads.mask_predictor = MaskRCNNPredictor(in_features_mask,
                                                       hidden_layer,
                                                       num_classes)
    
    return model


# Optional for testing some aspects of training.
#import torchvision
#from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
#
# load a model pre-trained pre-trained on COCO
#model = torchvision.models.detection.fasterrcnn_resnet50_fpn(weights=True)
#
# replace the classifier with a new one, that has
# num_classes which is user-defined
#num_classes = 5  # 1 class (person) + background
# get number of input features for the classifier
#in_features = model.roi_heads.box_predictor.cls_score.in_features
# replace the pre-trained head with a new one
#model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes) 
#
#model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
#indices = torch.randperm(len(dataset)).tolist()
#dataset = torch.utils.data.Subset(dataset, indices[:-1])
#
## define training and validation data loaders
#data_loader = torch.utils.data.DataLoader(
#    dataset, batch_size=1, shuffle=True, num_workers=2,
#    collate_fn=utils.collate_fn)
#
#images,targets = next(iter(data_loader))
#images = list(image for image in images)
#targets = [{k: v for k, v in t.items()} for t in targets]
#output = model(images,targets)   # Returns losses and detections
#
#output  (returns:)
#{'loss_box_reg': tensor(0.0229, grad_fn=<DivBackward0>),
#'loss_classifier': tensor(0.0835, grad_fn=<NllLossBackward0>),
#'loss_objectness': tensor(0.8662, grad_fn=<BinaryCrossEntropyWithLogitsBackward0>),
#'loss_rpn_box_reg': tensor(0.4854, grad_fn=<DivBackward0>)}
###End Optional

# use our dataset and defined transformations
dataset = sensor_image(dir_in, get_transform(train=True))
dataset_test = sensor_image(dir_in, get_transform(train=False))

# split the dataset in train and test set
torch.manual_seed(1)
indices = torch.randperm(len(dataset)).tolist()
dataset = torch.utils.data.Subset(dataset, indices[:-1])
dataset_test = torch.utils.data.Subset(dataset_test, indices[-1:])

# define training and validation data loaders
data_loader = torch.utils.data.DataLoader(
    dataset, batch_size=1, shuffle=True, num_workers=2,
    collate_fn=utils.collate_fn)

data_loader_test = torch.utils.data.DataLoader(
    dataset_test, batch_size=1, shuffle=False, num_workers=2,
    collate_fn=utils.collate_fn)

device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

# get the model using our helper function
model = get_instance_segmentation_model(num_classes)
# move model to the right device
model.to(device)

# construct an optimizer. changed lr from 0.005 to 0.0001 to 0.001
params = [p for p in model.parameters() if p.requires_grad]
optimizer = torch.optim.SGD(params, lr=0.001,
                            momentum=0.9, weight_decay=0.0005)

# and a learning rate scheduler which decreases the learning rate by
# 10x every 3 epochs
lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer,
                                               step_size=3,
                                               gamma=0.1)

# let's train it for 10 epochs
num_epochs = 10

for epoch in range(num_epochs):
    # train for one epoch, printing every 10 iterations
    train_one_epoch(model, optimizer, data_loader, device, epoch, print_freq=10)
    # update the learning rate
    lr_scheduler.step()
    # evaluate on the test dataset
    evaluate(model, data_loader_test, device=device)

# https://pytorch.org/tutorials/beginner/saving_loading_models.html
# Save the model and its settings:

# state_dict holds the model parameters. Not sure if necessary due to next command,
# but this won't hurt.  
#torch.save(model.state_dict(), "/content/drive/MyDrive/APHIS Farm Bill (2020Milestones)/Protocols/For John/images/New set for John/collection/four_chambers/model/MaskModelParams_newlr.pth")

# Save "the whole model"
# "This save/load process uses the most intuitive syntax and involves the least 
# amount of code. Saving a model in this way will save the entire module using 
# Python’s pickle module. The disadvantage of this approach is that the 
# serialized data is bound to the specific classes and the exact directory 
# structure used when the model is saved. The reason for this is because pickle 
# does not save the model class itself. Rather, it saves a path to the file 
# containing the class, which is used during load time. Because of this, your 
# code can break in various ways when used in other projects or after refactors."
# Call "model.eval()" before saving. 
#torch.save(model, "/content/drive/MyDrive/APHIS Farm Bill (2020Milestones)/Protocols/For John/images/New set for John/collection/four_chambers/model/MaskInstanceModel_newlr.pth")

# Not sure what is supposed to go in the {}...
#torch.save({
#            'epoch': epoch,
#            'model_state_dict': model.state_dict(),
#            'optimizer_state_dict': optimizer.state_dict(),
#            'loss': loss,
#            ...
#            }, /content/drive/MyDrive/APHIS Farm Bill (2020Milestones)/Protocols/For John/images/New set for John/collection/four_chambers/model/)

#torch.save({
#            'epoch': epoch,
#            'model_state_dict': model.state_dict(),
#            'optimizer_state_dict': optimizer.state_dict(),
#            'model_frame': model,
#            }, '/content/drive/MyDrive/APHIS Farm Bill (2020Milestones)/Protocols/For John/images/New set for John/collection/four_chambers/model/wholemodel_newlr.pth')

print("Model's state_dict:")
for param_tensor in model.state_dict():
    print(param_tensor, "\t", model.state_dict()[param_tensor].size())

print("Optimizer's state_dict:")
for var_name in optimizer.state_dict():
    print(var_name, "\t", optimizer.state_dict()[var_name])

dataset_test[3][0].shape

# pick one image from the test set
img, _ = dataset_test[0]
# put the model in evaluation mode
model.eval()
with torch.no_grad():
    prediction = model([img.to(device)])

# This tests the model with completely new images I created by manually
# manipulating the images in the original set.

from torchvision.io import read_image
from torchvision.transforms.functional import convert_image_dtype

dog1_int = read_image('/content/drive/MyDrive/APHIS Farm Bill (2020Milestones)/Protocols/For John/images/New set for John/collection/four_chambers/newtestimgs/set100m_vh_4.png')
dog2_int = read_image('/content/drive/MyDrive/APHIS Farm Bill (2020Milestones)/Protocols/For John/images/New set for John/collection/four_chambers/newtestimgs/set100m_vh_5.png')


# The data need to be converted to GPU, or cuda, compatible. 
# An example of loading model and data:
#device = torch.device("cuda")
#model = TheModelClass(*args, **kwargs)
#model.load_state_dict(torch.load(PATH))
#model.to(device)
# Make sure to call input = input.to(device) on any input tensors that you feed to the model

dog1 = dog1_int.to(device)
dog2 = dog2_int.to(device)

batch_int = torch.stack([dog1, dog2])
batch = convert_image_dtype(batch_int, dtype=torch.float)

new_dat = model(batch)

new_dat[0]

img1 = Image.fromarray(dog1_int.permute(1, 2, 0).byte().numpy())

plt.imshow(img1)
ax = plt.gca()
ax.grid(True, color='r', linestyle='--')
plt.draw()
plt.show()

pred1 = Image.fromarray(new_dat[0]['masks'][0, 0].mul(255).byte().cpu().numpy())

plt.imshow(pred1)
ax = plt.gca()
ax.grid(True, color='w', linestyle='--')
plt.draw()
plt.show()

pred1 = Image.fromarray(new_dat[0]['masks'][1, 0].mul(255).byte().cpu().numpy())

plt.imshow(pred1)
ax = plt.gca()
ax.grid(True, color='w', linestyle='--')
plt.draw()
plt.show()

pred1 = Image.fromarray(new_dat[0]['masks'][2, 0].mul(255).byte().cpu().numpy())

plt.imshow(pred1)
ax = plt.gca()
ax.grid(True, color='w', linestyle='--')
plt.draw()
plt.show()

pred1 = Image.fromarray(new_dat[0]['masks'][3, 0].mul(255).byte().cpu().numpy())

plt.imshow(pred1)
ax = plt.gca()
ax.grid(True, color='w', linestyle='--')
plt.draw()
plt.show()

img3 = Image.fromarray(dog2_int.permute(1, 2, 0).byte().numpy())

plt.imshow(img3)
ax = plt.gca()
ax.grid(True, color='r', linestyle='--')
plt.draw()
plt.show()

pred1 = Image.fromarray(new_dat[1]['masks'][0, 0].mul(255).byte().cpu().numpy())

plt.imshow(pred1)
ax = plt.gca()
ax.grid(True, color='w', linestyle='--')
plt.draw()
plt.show()

pred1 = Image.fromarray(new_dat[1]['masks'][1, 0].mul(255).byte().cpu().numpy())

plt.imshow(pred1)
ax = plt.gca()
ax.grid(True, color='w', linestyle='--')
plt.draw()
plt.show()

pred1 = Image.fromarray(new_dat[1]['masks'][2, 0].mul(255).byte().cpu().numpy())

plt.imshow(pred1)
ax = plt.gca()
ax.grid(True, color='w', linestyle='--')
plt.draw()
plt.show()

pred1 = Image.fromarray(new_dat[1]['masks'][3, 0].mul(255).byte().cpu().numpy())

plt.imshow(pred1)
ax = plt.gca()
ax.grid(True, color='w', linestyle='--')
plt.draw()
plt.show()

pred1 = Image.fromarray(new_dat[1]['masks'][4, 0].mul(255).byte().cpu().numpy())

plt.imshow(pred1)
ax = plt.gca()
ax.grid(True, color='w', linestyle='--')
plt.draw()
plt.show()
