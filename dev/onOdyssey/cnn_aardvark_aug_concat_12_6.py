
from __future__ import print_function
#import keras
from keras.datasets import cifar10
from keras.preprocessing.image import ImageDataGenerator
from keras.models import Model
from keras.layers import Input, Dense, Dropout, Activation, Flatten
from keras.layers import Conv2D, MaxPooling2D, AveragePooling2D, concatenate
from keras.callbacks import EarlyStopping
from keras.optimizers import Adam
from keras.utils import to_categorical
from keras.models import load_model
import os
import numpy as np
from sklearn.model_selection import LeaveOneOut,StratifiedKFold, train_test_split
#from sklearn.utils.class_weight import compute_class_weight
import math
import random
from sklearn.metrics import confusion_matrix
from scipy import ndimage
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument('-e', action='store_true', dest='use_extracted', 
    help='also input the mannually extracted properties from SEP')
parser.add_argument('-t', action='store_true', dest='test',
    help='for testing purposes, pass in the answers in place of the manually extracted properties')
parser.add_argument('-b', nargs=1, type=int, 
    help='batch size')
parser.add_argument('-p', nargs=1, type=int, dest='pooling',
    help='add extra pooling layer of this factor')
parser.add_argument('-d', nargs=1, type=float, dest='dropout',
    help='add extra dropout layer of this factor, default 0.25')
parser.add_argument('-c', action='store_true', dest='conv',
    help='add extra conv layer?')
parser.add_argument('-m', nargs=1, type=int,
    help='model number for naming.')
parser.add_argument('-n', nargs=1, type=int,
    help='number of epochs')
parser.add_argument('-s', action='store_true', dest='save',
    help='save model and results? DO NOT USE WITH SIMULTANEOUS RUNS')
parser.add_argument('-a', action='store_true', dest='ia_only',
    help='classify ia vs. other only')
parser.add_argument('-l', nargs=1, type=float,
    help='learning rate')
parser.add_argument('--no_sls', action='store_true', dest='no_sls',
    help='remove sls from sample')
parser.add_argument('--alt', action='store_true', dest='use_alt',
    help='MIGHT BE ALTERNATE VALIDATION SET use alternate shuffle (seed_offset 10)')
parser.add_argument('-3', action='store_true', dest='three_categories',
    help='classify between three categories: ia; ii and iin; ibc and sls')
parser.add_argument('--mask', action='store_true',
    help='include most likely host mask layer')
parser.add_argument('--mp', nargs=1, type=int, dest='mean_pooling',
    help='add an extra mean pooling layer of this factor')
parser.add_argument('--kfold', nargs = 1, type=int, default='-1', dest='k_fold',
    help='use kfold crossval with 4 folds')
args = parser.parse_args() 
print(sys.argv)
#print(args.dropout)
#TODO move utils to separate file

'''DEPRECATED'''
def augment_old(images, num):
    print("augmenting")
    print(len(images))
    aug_images = list(images)
    rots = np.array(range(1, 40))*360/40
    random.shuffle(rots)
    m = 39/len(images)
    for i in range(100):
        for j in range(len(images)):
            if len(aug_images) >= num:
                print("returning")
                return aug_images
            else:
                aug_images.append(ndimage.rotate(images[j], rots[int((i*m +j) % 39)], reshape=False))


def augment(images, corresponding_properties, num, rotate=True):
  
    aug_images = []#list(images)
    aug_props = list(corresponding_properties)
    l = len(images)
    #if l > num:
    #    aug_images = aug_images[:num]
    #    aug_props = aug_props[:num]
    for i in range(num):# - l):
        image = images[i % l]
        if rotate:
            image = ndimage.rotate(image, 360*random.random(), reshape=False)
            if random.random() > 0.5:
                image = np.flipud(image)
            if random.random() > 0.5:
                image = np.fliplr(image)
        aug_images.append(image)
    if args.use_extracted:
        raise
#TODO Restore!!!!!
        #aug_props.append(corresponding_properties[i%l])
    return (aug_images, aug_props)
            

def shuffle(X, y, X_sep=None):
    X = np.array(X)
    y = np.array(y)
    if len(X) != len(y):
        raise Exception("shuffle received unequal length arguments")
    new_ind = np.random.permutation(len(y))
    
    if X_sep:
        X_sep = np.array(X_sep)
        if len(X) != len(X_sep):
            print(len(X))
            print(len(X_sep))
#TODO RESTORE!!!!!!!!!!!!!!!!
            pass#raise Exception("shuffle x_sep uneqal lengths")
        if args.use_extracted:
            raise
        #TODO restore!!!!!!!
        return (X[new_ind, :], y[new_ind], [])#X_sep[new_ind, :])
    else:
        return (X[new_ind, :], y[new_ind])
#TODO check axes
        
def load_fixed_kfold(ia_only=False, three=False, mask=False, num_splits=12, 
                     seed_offset=0):
    n_ia = len(np.load("x_all2_0.npy"))
    n_ibc = len(np.load("x_all2_1.npy"))
    n_ii = len(np.load("x_all2_2.npy"))
    n_iin = len(np.load("x_all2_3.npy"))
    n_sls = len(np.load("x_all2_4.npy"))
    n_tot = n_ia + n_ibc + n_ii + n_iin + n_sls 
    
    if ia_only:
        #aug_to = [286, 38, 183, 43, 22]
        aug_to = [n_ia, 
                    np.round(n_ia*n_ibc/(n_tot - n_ia)), 
                    np.round(n_ia*n_ii/(n_tot - n_ia)),
                    np.round(n_ia*n_iin/(n_tot - n_ia)),
                    np.round(n_ia*n_sls/(n_tot - n_ia))]
    elif three:
        #aug_to = [286, 183, 231, 55, 103]
        aug_to = [n_ia, 
                    np.round(n_ia*n_ibc/(n_ibc+n_sls)),
                    np.round(n_ia*n_ii/(n_ii+n_iin)),
                    np.round(n_ia*n_iin/(n_ii+n_iin)),
                    np.round(n_ia*n_sls/(n_ibc+n_sls))]
    else:
        aug_to = [n_ia]*5

    X_train_folds = []
    y_train_folds = []
    X_test_folds = []
    y_test_folds = []
    for i in range(num_splits):
        X_train_folds.append([])
        y_train_folds.append([])
        X_test_folds.append([])
        y_test_folds.append([])
    for i in range(5):
        NUM = int(aug_to[i])
        print(NUM)
        if mask:
            print("using mask")
            raw = np.load("x_all2_%s.npy" % i).astype('float32')/1000000.
            raw_sep = np.load("x_ans_%s.npy" % i).astype('float32')/1000000.
        else:
            raw = np.load("x_all_%s.npy" % i).astype('float32')/1000000.
            raw_sep = np.load("x_ans_%s.npy" % i).astype('float32')/1000000.
            
        random.seed(i + seed_offset)
        random.shuffle(raw)
        random.seed(i+seed_offset)
        random.shuffle(raw_sep)
        
        #this is dumb, don't need stratification, but ok        
        folds = list(StratifiedKFold(n_splits=num_splits, shuffle=True, 
                                     random_state=1).split(raw, [i]*len(raw)))
        for j, (train, test) in enumerate(folds):
            print(raw[train].shape)
#TODO this has been changed from the sep
            train_aug, train_aug_sep = augment(raw[train], [0]*len(train), NUM)
            print((np.array(train_aug)).shape)
            X_train_folds[j].extend(crop(train_aug))
            y_train_folds[j].extend([i]*len(train_aug))
            
            test_aug, test_aug_sep = augment(raw[test], [0]*len(train), len(raw[test]))            
            X_test_folds[j].extend(crop(test_aug))
            y_test_folds[j].extend([i]*len(test_aug))
                     
    extrastring = str(seed_offset) if seed_offset>0 else ''
    if True:#k_fold
        filname = "aug_all"
    else:
        filname = "aug_load_output_3"

    if ia_only:
        filname = filname + "_ia"
    elif three:
        filname = filname + "_three_cats"
    if mask:
        filname = filname + "_mask"   
        
    for j in range(len(y_train_folds)):
        np.savez(filname+extrastring+'_fold_%s'%j, 
                 X_train_folds[j], y_train_folds[j], 
                 X_test_folds[j], y_test_folds[j])
        

            
def crop(ls):
    a = np.array(ls)
    print(a.shape)
    b = a[:, 40:-40, 40:-40]
    return(list(b))
            
        

def load(answers=False, ia_only=False, three=False, seed_offset=0, crop=True, 
             mask=False, k_fold=False):
    raise Exception("THIS FUNCTION IS PROBABLY ERRONEOUS")
    if ia_only and three:
        print("CANT DO IA AND THREE")
        exit(1)

    X_test = []
    X_train = []
    X_val = []
    y_test = []
    y_train = []
    y_val = []
    Xsep_test = []
    Xsep_train = []
    Xsep_val = []
    
    
    X_full = []
    y_full = []
    Xsep_full = []
    
    n_ia = 333
    n_ibc = 16
    n_ii = 85
    n_iin = 24
    n_sls = 12
    n_tot = n_ia + n_ibc + n_ii + n_iin + n_sls 
    #NUM should be total number of samples in largest class
    if ia_only:
        #aug_to = [286, 38, 183, 43, 22]
        aug_to = [n_ia, 
                    np.round(n_ia*n_ibc/(n_tot - n_ia)), 
                    np.round(n_ia*n_ii/(n_tot - n_ia)),
                    np.round(n_ia*n_iin/(n_tot - n_ia)),
                    np.round(n_ia*n_sls/(n_tot - n_ia))]
    elif three:
        #aug_to = [286, 183, 231, 55, 103]
        aug_to = [n_ia, 
                    np.round(n_ia*n_ibc/(n_ibc+n_sls)),
                    np.round(n_ia*n_ii/(n_ii+n_iin)),
                    np.round(n_ia*n_iin/(n_ii+n_iin)),
                    np.round(n_ia*n_sls/(n_ibc+n_sls))]
    else:
        aug_to = [n_ia]*5

    for i in range(5):
        if True: #ia_only:
            NUM = int(aug_to[i])
            print(NUM)
        if mask:
            print("using mask")
            raw = np.load("x_all2_%s.npy" % i).astype('float32')/1000000.
            raw_sep = np.load("x_ans_%s.npy" % i).astype('float32')/1000000.
        else:
            raw = np.load("x_all_%s.npy" % i).astype('float32')/1000000.
            raw_sep = np.load("x_ans_%s.npy" % i).astype('float32')/1000000.

        print(len(raw))
        random.seed(i + seed_offset)
        random.shuffle(raw)
        random.seed(i+seed_offset)
        random.shuffle(raw_sep)
        
        if k_fold:
            print(NUM)
            print(type(NUM))
            fulli, fullp = augment(raw, raw_sep, NUM)
            X_full.extend(fulli)
            Xsep_full.extend(fullp)
            y_full.extend([i]*len(fulli))
        else:
#TODO handpick which goes in which
#TODO augment up to appropriate numbers
        #div = math.floor(len(raw)/3)
            div = math.floor(0.2*len(raw))
        #div = max(div, 4)
#TODO fix len below
#TODO if div is floored to 4, the use of 0.6*NUM below doesn't work correctly
#wait maybe it does
#TODO fix this stupid hardcoding
        #if FOLD==0:
#TODO do we want to rotate test and val sets below but just have a few rotations of them?
            testi, testp = augment(raw[:div], raw_sep[:div], int(0.2*NUM), rotate=False)#len(raw[:div])))
            vali, valp = augment(raw[div:2*div], raw_sep[div:2*div], int(0.2*NUM), rotate=False)#len(raw[div:2*div]))#int(0.2*NUM))
            traini, trainp = augment(raw[2*div:], raw_sep[2*div:], int(0.6*NUM))
            X_test.extend(testi)
            y_test.extend([i]*len(testi))
            Xsep_test.extend(testp)
            X_train.extend(traini)
            y_train.extend([i]*len(traini))
            Xsep_train.extend(trainp)
            X_val.extend(vali)
            y_val.extend([i]*(len(vali)))
            Xsep_val.extend(valp)
    if crop:
        if k_fold: 
            X_full = np.array(X_full)
            X_full = X_full[:, 40:-40, 40:-40]
        else:
            X_val = np.array(X_val)
            X_test = np.array(X_test)
            X_train = np.array(X_train)
            X_val = X_val[:, 40:-40, 40:-40]
            X_test = X_test[:, 40:-40, 40:-40]
            X_train = X_train[:, 40:-40, 40:-40]
    if k_fold:
        X_full, y_full, Xsep_full = shuffle(X_full, y_full, Xsep_full)
    else:
        X_test, y_test, Xsep_test = shuffle(X_test, y_test, Xsep_test)
        X_train, y_train, Xsep_train = shuffle(X_train, y_train, Xsep_train)    
        X_val, y_val, Xsep_val = shuffle(X_val, y_val, Xsep_val)       
    if not ia_only:
        np.save("y_test_aardvark_aug"+model_num+str(seed_offset), y_test)
    extrastring = str(seed_offset) if seed_offset>0 else ''
    if k_fold:
        filname = "aug_all"
    else:
        filname = "aug_load_output_3"

    if ia_only:
        filname = filname + "_ia"
    elif three:
        filname = filname + "_three_cats"

    if mask:
        print('mask')
        filname = filname + "_mask"

    if k_fold:
        np.savez(filname+extrastring, X_full, Xsep_full, y_full)
    else:
        np.savez(filname+extrastring, X_test, y_test, Xsep_test, X_train, y_train, Xsep_train, X_val, y_val, Xsep_val) 
# 
#        if k_fold:
#            np.savez("aug_all_ia"+extrastring, X_full, Xsep_full, y_full)
#        else:
#            np.savez("aug_load_output_ia3"+extrastring, X_test, y_test, Xsep_test, X_train, y_train, Xsep_train, X_val, y_val, Xsep_val) 
#    elif three:    
#        if k_fold:
#            np.savez("aug_all_three_cats"+extrastring, X_full, Xsep_full, y_full)
#        else:
#            np.savez("aug_load_output_three_cats"+extrastring, X_test, y_test, Xsep_test, X_train, y_train, Xsep_train, X_val, y_val, Xsep_val)   
#    elif mask:
#        if k_fold:
#            np.savez("aug_all_mask"+extrastring, X_full, Xsep_full, y_full)
#        else:
#            np.savez("aug_load_output_3_mask"+extrastring, X_test, y_test, Xsep_test, X_train, y_train, Xsep_train, X_val, y_val, Xsep_val)  
#
#    else:
# 
#        if k_fold:
#            np.savez("aug_all"+extrastring, X_full, Xsep_full, y_full)
#        else:
#            np.savez("aug_load_output_3"+extrastring, X_test, y_test, Xsep_test, X_train, y_train, Xsep_train, X_val, y_val, Xsep_val)  

    return#(X_test, y_test, Xsep_test, X_train, y_train, Xsep_train, X_val, y_val, Xsep_val)   

def make_splits(filename, num_splits):
    raise Exception("this should be deprecated")
    arrs = np.load(filename)
    X_full = arrs['arr_0']
    y_full = arrs['arr_2']
    folds = list(StratifiedKFold(n_splits=num_splits, shuffle=True, random_state=1).split(X_full, y_full))
    for j, (train, test) in enumerate(folds):
        np.savez(filename[:-4]+'_fold_%s'%j, X_full[train], y_full[train], X_full[test], y_full[test])



def main():

    if args.test:
        print("TEST NOT YET IMPLEMENTED")

    no_sls = args.no_sls

    if args.k_fold[0] >= 0:
        k_folded=True
        fold_num = args.k_fold[0]
    if args.m:
        model_num = str(args.m[0])
    else:
        model_num= '11'

    if args.l:
        LR = float(args.l[0])
    else:
        LR = 0.0005

    ia_only = args.ia_only
    three_categories = args.three_categories


    USE_SAVED = False
    #TODO restore
    if args.ia_only:
        num_classes = 2
    elif three_categories:
        num_classes = 3
    else:
        num_classes = 5

    if args.n:
        epochs = args.n[0]
    else:
    #TODO restore
        epochs = 35
    #num_predictions = 20
    save_dir = os.path.join(os.getcwd(), 'saved_models')
    model_name = 'aardvark_aug' + model_num + '.h5'



    if (args.use_extracted  or args.mask) and ia_only:
        raise(ValueError, "NOT YET IMPLEMENTED IA WITH EXTRACTED")
        exit(1)

    #x_train = np.load("x_all.npy")
    #y_train = np.load("y_all.npy")
#TODO restore

    if k_folded:
        filname = "aug_all"
    else:
        filname = "aug_load_output_3"

    if ia_only:
        filname = filname + "_ia"
    elif three_categories:
        filname = filname + "_three_cats"

    if args.mask:
        filname = filname + "_mask"

    if k_folded:
        filname = filname + "_fold_%s"%fold_num
    all_data = np.load(filname + '.npz')
    
    if k_folded:
        print(1)
#        if ia_only:
#            all_data = np.load("aug_all_ia.npz")
#        elif args.use_alt:
#            raise Exception("don't use alt with k_fold")
#        elif args.mask:
#            all_data = np.load("aug_all_mask_fold_%s.npz" % fold_num)
#
#        elif three_categories:
#            all_data = np.load("aug_all_three_cats.npz")
#        else:
#            all_data =  np.load("aug_all_fold_%s.npz" % fold_num) #load()
        #X_full = all_data['arr_0']
        #Xsep_full = all_data['arr_1']
        #y_full = all_data['arr_2']
        X_full_train = all_data['arr_0']
        y_full_train = all_data['arr_1']
        X_full_test = all_data['arr_2']
        y_full_test = all_data['arr_3']

        if ia_only: 
            y_full_train = np.where(y_full_train==0, 0, 1)
            y_full_test = np.where(y_full_test==0, 0, 1)
    
        if three_categories:
            raise
            #make all sls into ibc
            #y_full = np.where(y_full==4, 1, y_full)
            
            #make all iin into ii
            #y_full = np.where(y_full==3, 2, y_full)
    
        if no_sls:
            raise
            #y_full_orig = y_full
            #y_full = y_full[y_full_orig != 4]
            #X_full = X_full[y_full_orig != 4]

        #y_full_orig = y_full
        #y_full = to_categorical(y_full, num_classes)
        y_full_test_orig = y_full_test
        y_full_train = to_categorical(y_full_train, num_classes)
        y_full_test = to_categorical(y_full_test, num_classes)

   
    else:
#        if ia_only:
#            all_data = np.load("aug_load_output_ia3.npz")
#        elif args.use_alt:
#            if args.mask:
#                all_data = np.load("aug_load_output_10_mask.npz")
#            else:
#                all_data = np.load("aug_load_output_10.npz")
#            print("loaded")
#        elif args.mask:
#            all_data = np.load("aug_load_output_mask.npz")
#    
#        elif three_categories:
#            all_data = np.load("aug_load_output_three_cats.npz")
#        else:
#            all_data =  np.load("aug_load_output3.npz") #load()
        X_test = all_data['arr_0'] 
        y_test= all_data['arr_1']
        Xsep_test = all_data['arr_2']
        X_train= all_data['arr_3']
        y_train= all_data['arr_4']
        Xsep_train= all_data['arr_5']
        X_val= all_data['arr_6']
        y_val= all_data['arr_7']
        Xsep_val= all_data['arr_8']
   
        if ia_only: 
            y_train = np.where(y_train==0, 0, 1)
            y_test = np.where(y_test==0, 0, 1)
            y_val = np.where(y_val==0, 0, 1)
    
        if three_categories:
            #make all sls into ibc
            y_train = np.where(y_train==4, 1, y_train)
            y_test = np.where(y_test==4, 1, y_test)
            y_val = np.where(y_val==4, 1, y_val)
            
            #make all iin into ii
            y_train = np.where(y_train==3, 2, y_train)
            y_test = np.where(y_test==3, 2, y_test)
            y_val = np.where(y_val==3, 2, y_val)
    
        if no_sls:
            y_train_orig = y_train
            y_train = y_train[y_train_orig != 4]
            X_train = X_train[y_train_orig != 4]

        y_test_orig = y_test
        y_train = to_categorical(y_train, num_classes)
        y_test = to_categorical(y_test, num_classes)
        y_val = to_categorical(y_val, num_classes)
        
    if args.b:
        batch_size = args.b[0]
    else:
        batch_size = len(X_train)
    # Convert class vectors to binary class matrices.
    #y_train = keras.utils.to_categorical(y_train, num_classes)
    #y_test = keras.utils.to_categorical(y_test, num_classes)

    model_path = os.path.join(save_dir, model_name)
    def get_model(in1_shape, in2_shape):
        if USE_SAVED:
            return(load_model(model_path))
        else:
            input1 = Input(shape=in1_shape)
            if args.use_extracted:
                input2 = Input(shape=in2_shape)
            if args.conv:
                conv = Conv2D(32, (3, 3), padding='same')(input1)
                if args.dropout:
                    dropout_conv=Dropout(args.dropout[0])(conv)
                    prev_for_act1 = dropout_conv
                else:
                    prev_for_act1 = conv
                
                act1 = Activation('relu')(prev_for_act1)
                if args.dropout:
                    dropout_act1=Dropout(args.dropout[0])(act1)
                    prev_for_pool1 = dropout_act1
                else:
                    prev_for_pool1 = act1
                if args.mean_pooling:
                    pool1 = AveragePooling2D(pool_size=(2, 2))(prev_for_pool1)
                else:
                    pool1 = MaxPooling2D(pool_size=(2, 2))(prev_for_pool1)
                if args.dropout:
                    dropout_pool1=Dropout(args.dropout[0])(pool1)
                    prev_for_convb = dropout_pool1
                else:
                    prev_for_convb = pool1
    
    #TODO proofread this whole section
                convb = Conv2D(32, (3, 3), padding='same')(prev_for_convb)
                if args.dropout:
                    dropout_convb=Dropout(args.dropout[0])(convb)
                    prev_for_act1b = dropout_convb
                else:
                    prev_for_act1b = convb
                
                act1b = Activation('relu')(prev_for_act1b)
                if args.dropout:
                    dropout_act1b=Dropout(args.dropout[0])(act1b)
                    prev_for_pool1b = dropout_act1b
                else:
                    prev_for_pool1b = act1b
                if args.mean_pooling:
                    pool1b = AveragePooling2D(pool_size=(2, 2))(prev_for_pool1b)
                else:
                    pool1b = MaxPooling2D(pool_size=(2, 2))(prev_for_pool1b)
                if args.dropout:
                    dropout_pool1b=Dropout(args.dropout[0])(pool1b)
                    prev_for_conv2 = dropout_pool1b
                else:
                    prev_for_conv2 = pool1b
    
    
            else:
                prev_for_conv2=input1
            
            conv2 = Conv2D(32, (3, 3), padding='same')(prev_for_conv2)
            if args.dropout:
                dropout_conv2=Dropout(args.dropout[0])(conv2)
                prev_for_act2 = dropout_conv2
            else:
                prev_for_act2 = conv2
    
            act2 = Activation('relu')(prev_for_act2)
            if args.dropout:
                dropout_act2=Dropout(args.dropout[0])(act2)
                prev_for_pool2= dropout_act2
            else:
                prev_for_pool2 = act2
            if args.mean_pooling:
                pool2 = AveragePooling2D(pool_size=(2, 2))(prev_for_pool2)
            else:
                pool2 = MaxPooling2D(pool_size=(2, 2))(prev_for_pool2)
            
            if args.pooling:
                pool3 = MaxPooling2D(pool_size=(args.pooling[0], args.pooling[0]))(pool2)
                flatten=Flatten()(pool3)
            elif args.mean_pooling:
                pool3 = AveragePooling2D(pool_size=(args.mean_pooling[0], args.mean_pooling[0]))(pool2)
                flatten=Flatten()(pool3)
            #model.add(Dropout(0.25))
            else:
                flatten = Flatten()(pool2)
            if args.dropout:
                dropout = Dropout(args.dropout[0])(flatten)
                dense1 = Dense(512, activation=('relu'))(dropout)
            else:
                dense1 = Dense(512, activation=('relu'))(flatten)
            #model.add(Dropout(0.5))
            if args.use_extracted:
                concat = concatenate([dense1, input2], axis=-1)
                dense2 = Dense(num_classes, activation=('softmax'))(concat)
            else:
                dense2 = Dense(num_classes, activation=('softmax'))(dense1)
            # initiate RMSprop optimizer
            opt = Adam(lr=LR)
            #TODO check above
    
            # Let's train the model using RMSprop
            if args.use_extracted:
                ins = [input1, input2]
            else:
                ins = input1
            model = Model(input=ins, output=dense2)
            model.compile(loss='categorical_crossentropy',
                  optimizer=opt,
                  metrics=['accuracy'])
            return model

    es = EarlyStopping(monitor='val_acc', patience=50, verbose=1, baseline=0.4, restore_best_weights=True)

    if k_folded:
        print(2)
        if args.use_extracted:
            raise("not yet implemented")
#        y_pred_folded = []
#        y_true_folded = []
#        folds = list(StratifiedKFold(n_splits=4, shuffle=True, random_state=1).split(y_full_orig, y_full_orig))
#        for j, (train_index, test_index) in enumerate(folds):
#            print('\nFold ',j)
#            X_train_fold = X_full[train_index]
#            y_train_fold = y_full[train_index]
#            X_test_fold = X_full[test_index]
#            y_test_fold = y_full[test_index]
#            model = get_model(in1_shape=X_full.shape[1:], in2_shape=Xsep_full.shape[1:])
#            model.fit(x=X_train_fold, y=y_train_fold,
#                  batch_size=batch_size,
#                  epochs=epochs,
#                  validation_data=(X_test_fold, y_test_fold),
#                  shuffle=True)
#            y_pred_folded.extend(list(model.predict(X_test_fold)))
#            y_true_folded.extend(list(y_test_fold))
#TODO fix in2_shape
        model = get_model(in1_shape=X_full_train.shape[1:], in2_shape=X_full_train.shape[1:])
        model.fit(x=X_full_train, y=y_full_train,
              batch_size=batch_size,
              epochs=epochs,
              validation_data=(X_full_test, y_full_test),
              shuffle=True)
        y_pred = model.predict(X_full_test)
        y_pred_2 = np.argmax(y_pred, 1)
        print(y_pred)
        arglist = sys.argv
        namestr = 'y_pred_from_'
        for ar in arglist:
            namestr = namestr + '_' + ar.replace('-','')
        np.save(namestr, y_pred)
        print('saved: %s'%namestr)
        cm = confusion_matrix(y_full_test_orig, y_pred_2)
        print(cm)
        

    else:
        if args.use_extracted:
            model = get_model(in1_shape = X_train.shape[1:], in2_shape = Xsep_train.shape[1:])
            model.fit(x=[X_train, Xsep_train], y=y_train,
                  batch_size=batch_size,
                  epochs=epochs,
                  validation_data=([X_val, Xsep_val], y_val),
                  callbacks = [es],
                  #sample_weight=sampleweights,
                  shuffle=True)
        else:
#TODO fix in2_shape
            model = get_model(in1_shape = X_train.shape[1:], in2_shape = X_train.shape[1:])
            model.fit(x=X_train, y=y_train,
                  batch_size=batch_size,
                  epochs=epochs,
                  validation_data=(X_val, y_val),
                  callbacks = [es],
#TODO restore
                  #sample_weight=sampleweights,
                  shuffle=True)
            # Save model and weights
            if not os.path.isdir(save_dir):
                os.makedirs(save_dir)
            model_path = os.path.join(save_dir, model_name)
            if args.save:
                model.save(model_path)
            print('Saved trained model at %s ' % model_path)
        
        if args.use_extracted:
            y_pred = model.predict([X_test, Xsep_test])
        else:
            y_pred = model.predict(X_test)
        y_pred2 = np.argmax(y_pred, 1)
        if args.save:
            np.save("y_pred_aardvark25weighted_aug"+model_num, y_pred2)
            np.save("y_test", y_test)

        cm = confusion_matrix(y_test_orig, y_pred2)
        print(cm)
        if args.save:
            np.save("cm_aa"+model_num, cm, allow_pickle=True, fix_imports=True)
#    print(y_pred)
#    print(y_pred2)
    # Score trained model.
#    if args.use_extracted:
#        scores = model.evaluate([X_test, Xsep_test], y_test, verbose=1)
#    else:
#        scores = model.evaluate(X_test, y_test, verbose=1)
#    print('Test loss:', scores[0])
#    print('Test accuracy:', scores[1])

if __name__ == "__main__":
    main()
