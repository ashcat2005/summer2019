'''NOTE I forgot about the need to balance class weights in data generation.
May need to use "flow" fxn instead'''
from __future__ import print_function
import keras
from keras.datasets import cifar10
from keras.preprocessing.image import ImageDataGenerator
from keras.models import Sequential
from keras.layers import Dense, Dropout, Activation, Flatten
from keras.layers import Conv2D, MaxPooling2D
import os
import numpy as np
from sklearn.utils.class_weight import compute_class_weight
import math
import random
def augment(images, num):
    aug_images = list(images)
    rots = np.array(range(1, 40))*360/40
    random.shuffle(rots)
    m = 39/len(images)
    for i in range(39):
        for j in range(len(images)):
            if len(aug_images) >= num:
                return aug_images
            else:
                aug_images.append(ndimage.rotate(images[j], rots[int((i*m +j) % 39)], reshape=False))
                
USE_SAVED = False

num_classes = 5
epochs = 25
#num_predictions = 20
save_dir = os.path.join(os.getcwd(), 'saved_models')
model_name = 'aardvark_aug.h5'

# The data, split between train and test sets:
#(x_train, y_train), (x_test, y_test) = cifar10.load_data()
#print('x_train shape:', x_train.shape)
#print(x_train.shape[0], 'train samples')
#print(x_test.shape[0], 'test samples')

x_train = np.load("x_all.npy")
y_train = np.load("y_all.npy")
y_orig = y_train
y_train = keras.utils.to_categorical(y_train, num_classes)
batch_size = len(x_train)
# Convert class vectors to binary class matrices.
#y_train = keras.utils.to_categorical(y_train, num_classes)
#y_test = keras.utils.to_categorical(y_test, num_classes)

model_path = os.path.join(save_dir, model_name)
if USE_SAVED:
    model = keras.models.load_model(model_path)
else:
    model = Sequential()
    model.add(Conv2D(32, (3, 3), padding='same',
                     input_shape=x_train.shape[1:]))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    #model.add(Dropout(0.25))

    model.add(Flatten())
    model.add(Dense(512))
    model.add(Activation('relu'))
    #model.add(Dropout(0.5))
    model.add(Dense(num_classes))
    model.add(Activation('softmax'))

    # initiate RMSprop optimizer
    opt = keras.optimizers.Adam(lr=0.001)
    #TODO check above

    # Let's train the model using RMSprop
    model.compile(loss='categorical_crossentropy',
                  optimizer=opt,
                  metrics=['accuracy'])

    x_train = x_train.astype('float32')
    #x_test = x_test.astype('float32')
    x_train /= 1000000
    #x_test /= 255

    #make balanced class weights
    a = compute_class_weight('balanced', np.unique(y_orig), y_orig)
    datagen = ImageDataGenerator(
        rotation_range=180,  # randomly rotate images in the range (degrees, 0 to 180))
        horizontal_flip=True,  # randomly flip images
        vertical_flip=True)  # randomly flip images
    
    datagen.fit(X_train)

    # Save model and weights
    if not os.path.isdir(save_dir):
        os.makedirs(save_dir)
    model_path = os.path.join(save_dir, model_name)
    model.save(model_path)
    print('Saved trained model at %s ' % model_path)
y_pred = model.predict(x_train)
y_pred2 = np.argmax(y_pred, 1)
np.save("y_pred_aardvark25weighted_aug", y_pred2)
print(y_pred)
print(y_pred2)
# Score trained model.
scores = model.evaluate(x_train, y_train, verbose=1)
print('Test loss:', scores[0])
print('Test accuracy:', scores[1])
