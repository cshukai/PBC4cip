from abc import ABC, abstractmethod 
import os
import random
import math
import pandas as pd
import sys
import numpy as np
import pandas as pd
from .Helpers import get_col_dist
from .FileManipulation import GetFromFile, get_dataframe_from_arff

class Dataset(ABC):

    @property
    @abstractmethod
    def Instances(self):
        pass

    @property
    @abstractmethod
    def Attributes(self):
        pass

    @property
    @abstractmethod
    def Class(self):
        pass

    @property
    def AttributesInformation(self):
        return list(
            map(lambda attr: FeatureInformation(self, attr), self.Attributes))

    @property
    def ClassInformation(self):
        return FeatureInformation(self, self.Class)

    def GetAttribute(self, attribute):
        return list(filter(lambda attr: attr[0] == attribute, self.Model))[0]

    def GetAttributeNames(self):
        return list(
            map(lambda attribute: attribute[0], self.Model))
    
    def GetNominalValues(self, feature):
        attribute = list(
            filter(lambda attr: attr[0].lower() == feature.lower(), self.Model))

        if isinstance(attribute[0][1], list):
            return attribute[0][1]
        else:
            return None

    def GetValueOfIndex(self, feature, index):
        values = self.GetNominalValues(feature)
        if not values:
            return float('nan')
        else:
            return values[index]

    def GetIndexOfValue(self, feature, value):
        values = self.GetNominalValues(feature)
        if not values:
            return -1
        else:
            try:
                #print(f"values: {values}")
                return_val = values.index(value)
                return return_val
            except ValueError:
                return float('nan')

    def GetClasses(self):
        return self.GetNominalValues('class')

    def GetClassIdx(self):
        return self.GetFeatureIdx(self.Class)

    def GetFeatureIdx(self, feature):
        return self.Model.index(feature)
    
    def IsNominalFeature(self, feature):
        if isinstance(feature[1], str) and feature[1].lower() == 'string':
            raise Exception("String attributes are not supported!")
        return isinstance(feature[1], list)

    def GetFeatureValue(self, feature, instance):
        if isinstance(feature[1], list):
            return self.GetIndexOfValue(feature[0], instance[self.GetFeatureIdx(feature)])
        elif feature[1].lower() in ['numeric', 'real', 'integer']:
            return instance[self.GetFeatureIdx(feature)]
        else:
            raise Exception(
                "Attribute must be either nominal, numeric, real or integer")
    
    def GetClassValue(self, y_instance):
        return self.GetIndexOfValue(self.Class[0], y_instance[0])

    def IsMissing(self, feature, instance):
        value = self.GetFeatureValue(feature, instance)        
        return math.isnan(value)

class PandasDataset(Dataset):
    def __init__(self, X,y):
        #if (isinstance(Dataframe))
        super()
        self.Model = self.get_model_list(X,y)
        self.__Instances = self.combine_X_y(X,y)
    
    @property
    def Instances(self):
        return self.__Instances
    
    @property
    def Attributes(self):
        return list(
            filter(lambda attr: attr[0].strip().lower() != 'class', self.Model))

    @property
    def Class(self):
        return list(
            filter(lambda attr: attr[0].strip().lower() == 'class', self.Model))[0]
    
    @Instances.setter
    def Instances(self, new_instances):
        self.__Instances = new_instances

    def get_feature_info(self, feature):
        if self.get_feature_col_type(feature) == 'Nominal':
            return get_col_dist(feature)
        else:
            return self.get_feature_col_type(feature)
    def get_feature_col_type(self, feature):
        if all(isinstance(elem, np.int32) or isinstance(elem, np.int64) or isinstance(elem, int) for elem in feature):
            return 'integer'
        if all (isinstance(elem, np.float32) or isinstance(elem, np.float64) or isinstance(elem, float) for elem in feature):
            return 'real'
        else:
            return 'Nominal'

    def get_model_list(self, X, y):
        if 'class' in X.columns.values.tolist():
            raise Exception('No attribute can have the name class')

        result = [(feat_name, self.get_feature_info(X[f'{feat_name}'])) for feat_name in X]
        y = y.rename(columns = {y.columns.values.tolist()[0]: 'class'})
        y = pd.DataFrame(y)  
        class_res = [(feat_name, self.get_feature_info(y[f'{feat_name}'])) for feat_name in y]
        result.append(class_res[0])
        return result
    
    def combine_X_y(self, X, y):
        y = y.rename(columns = {y.columns.values.tolist()[0]: 'class'})
        y = pd.DataFrame(y)
        instances_df = X.copy(deep=True)
        instances_df[f'class'] = y['class']
        return instances_df.values
    """
    def GetClassValue(self, y_instance):
        print(f"aaa")
        print(f"y: {y_instance}")
        print(f"Class: {self.Class[0]} & y_inst: {y_instance[0]}")
        print(f"self: {self.GetIndexOfValue(self.Class[0], y_instance[0])}")
        return self.GetIndexOfValue(self.Class[0], y_instance[0])
    """
            

class FileDataset(Dataset):
    def __init__(self, file):
        super()
        arffFile = GetFromFile(file)

        attributes = arffFile['attributes']
        if not list(filter(lambda attr: attr[0].strip().lower() == 'class', attributes)):
            raise Exception(
                f"This dataset does not contain an explicit class attribute!")

        self.Relation = arffFile['relation']

        self.Model = arffFile['attributes']

        self.__Instances = get_dataframe_from_arff(arffFile).values
        self.Features = None
    
    @property
    def Instances(self):
        return self.__Instances
    
    @property
    def Attributes(self):
        return list(
            filter(lambda attr: attr[0].strip().lower() != 'class', self.Model))

    @property
    def Class(self):
        return list(
            filter(lambda attr: attr[0].strip().lower() == 'class', self.Model))[0]
    
    @Instances.setter
    def Instances(self, new_instances):
        self.__Instances = new_instances

    def ScalarProjection(self, instance, features, weights):

        if len(list(filter(lambda feature: self.IsMissing(feature, instance), features))) > 0:
            return math.nan

        result = sum([weights[feature] * self.GetFeatureValue(feature, instance)
                      for feature in features])

        return result

class FeatureInformation(object):
    def __init__(self, dataset, feature):
        self.__Dataset = dataset
        self.__Feature = feature
        self.__MinValue = 0
        self.__MaxValue = 0
        self.__Distribution = []
        self.__ValueProbability = []
        self.__Ratio = []

        self.Initialize()
    
    @property
    def Dataset(self):
        return self.__Dataset
    @Dataset.setter
    def Dataset(self, new_dataset):
        self.__Dataset = new_dataset

    @property
    def Feature(self):
        return self.__Feature

    @property
    def Distribution(self):
        return self.__Distribution
    @Distribution.setter
    def Distribution(self, new_distribution):
        self.__Distribution = new_distribution

    def Initialize(self):

        featureIdx = self.Dataset.GetFeatureIdx(self.Feature)

        nonMissingValues = list(filter(lambda instance: not self.Dataset.IsMissing(
            self.Feature, instance), self.Dataset.Instances))
        
        self.MissingValueCount = len(
            self.Dataset.Instances) - len(nonMissingValues)

        if self.Dataset.IsNominalFeature(self.Feature):

            self.Distribution = [0]*len(self.Feature[1])
            for value in range(len(self.Distribution)):
                self.Distribution[value] = len(
                    list(filter(lambda instance: self.Dataset.GetFeatureValue(self.Feature, instance) == value and not self.Dataset.IsMissing(self.Feature, instance), self.Dataset.Instances)))
            #self.ValueProbability = list(
                #map(lambda value: value / sum(self.Distribution), self.Distribution))
            
            #self.Ratio = list(
                #map(lambda value: value / min(self.Distribution), self.Distribution))

            

        else:
            if len(nonMissingValues) > 0:
                self.MinValue = min(list(map(
                    lambda instance: instance[featureIdx], nonMissingValues)))
                self.MaxValue = max(list(map(
                    lambda instance: instance[featureIdx], nonMissingValues)))
            else:
                self.MinValue = 0
                self.MaxValue = 0