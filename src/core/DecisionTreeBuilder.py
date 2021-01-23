import math
import random
from core.DecisionTree import DecisionTree, DecisionTreeNode
from core.WinningSplitSelector import WinningSplitSelector
from core.SplitIterator import SplitIterator
from core.Helpers import CreateMembershipTupleList, FindDistribution
from core.SplitIterator import SplitIteratorProvider, MultivariateSplitIteratorProvider
from core.ForwardFeatureIterator import ForwardFeatureIterator
from core.DistributionTester import PureNodeStopCondition, AlwaysTrue



class DecisionTreeBuilder():
    def __init__(self, dataset):
        self.MinimalInstanceMembership = 0.05
        self.MinimalSplitGain = 1e-30
        self.MinimalObjByLeaf = 2
        self.MaxDepth = -1
        self.PruneResult = False
        self.Dataset = dataset
        self.FeatureCount = 0
        self.StopCondition = PureNodeStopCondition
        self._distributionEvaluator = None
        self.OnSelectingFeaturesToConsider = None
        self.SplitIteratorProvider = SplitIteratorProvider(self.Dataset)
    
    @property
    def distributionEvaluator(self):
        return self._distributionEvaluator

    @distributionEvaluator.setter
    def distributionEvaluator(self, new_distributionEvaluator):
        self._distributionEvaluator = new_distributionEvaluator

    def Build(self):
        if self.MinimalSplitGain <= 0:
            print(f"MinimalSplitGain err in Build UniVariate")
            self.MinimalSplitGain = 1e-30

        currentContext = []


        objectMebership = CreateMembershipTupleList(self.Dataset.Instances)
        classFeature = self.Dataset.Class
        result = DecisionTree(self.Dataset)

        filteredObjMembership = list(
            filter(lambda x: x[1] >= self.MinimalInstanceMembership, objectMebership))

        parentDistribution = FindDistribution(
            filteredObjMembership, self.Dataset.Model, self.Dataset.Class)

        result.TreeRootNode = DecisionTreeNode(parentDistribution)
        self.FillNode(result.TreeRootNode,
                      filteredObjMembership, 0, currentContext)
        return result

    def FillNode(self, node, instanceTuples, level, currentContext):
        if self.StopCondition(node.Data, self.Dataset.Model, self.Dataset.Class):
            return
        if self.MaxDepth >= 0 and (level >= self.MaxDepth - 1):
            return
        if sum(node.Data) <= self.MinimalObjByLeaf:
            return
        
        whichBetterToFind = 1
        winningSplitSelector = WinningSplitSelector(whichBetterToFind)
        
        sampleFeatures = self.OnSelectingFeaturesToConsider(
            list(map(lambda attribute: attribute[0], self.Dataset.Attributes)), self.FeatureCount)

        for feature in sampleFeatures:
            if feature != self.Dataset.Class[0]:
                splitIterator = self.SplitIteratorProvider.GetSplitIterator(feature)
                splitIterator.Initialize(instanceTuples)
                while splitIterator.FindNext():
                    currentGain = self._distributionEvaluator(
                        node.Data, splitIterator.CurrentDistribution)
                    if currentGain >= self.MinimalSplitGain:
                        winningSplitSelector.EvaluateThis(
                            currentGain, splitIterator, level)
        if winningSplitSelector.IsWinner():
            maxSelector = winningSplitSelector.WinningSelector
            node.ChildSelector = maxSelector
            node.Children = list()
            instancesPerChildNode = CreateChildrenInstances(
                instanceTuples, maxSelector, self.MinimalInstanceMembership)

            for index in range(maxSelector.ChildrenCount):
                childNode = DecisionTreeNode(winningSplitSelector.WinningDistribution[index])
                childNode.Parent = node
                node.Children.append(childNode)

                self.FillNode(
                    childNode, instancesPerChildNode[index], level + 1, currentContext)

        return


def CreateChildrenInstances(instances, selector, threshold):

    result = list()
    for child in range(selector.ChildrenCount):
        result.append(list(tuple()))

    for instance in instances:
        selection = selector.Select(instance[0])
        if selection is not None:
            for index in range(len(selection)):
                if selection[index] > 0:
                    newMembership = selection[index] * instance[1]
                    if newMembership >= threshold:
                        result[index].append(
                            tuple((instance[0], newMembership)))

    return result



class SelectorContext():
    def __init__(self):
        self.Index = 0
        self.Selector = None


class MultivariateDecisionTreeBuilder(DecisionTreeBuilder):
    def __init__(self, dataset):
        super().__init__(dataset)
        self.MinimalForwardGain = 0
        self.WMin = 0  # Minimal absolute value for each weight after normalizing
        self.SplitIteratorProvider = MultivariateSplitIteratorProvider(
            self.Dataset)

    def Build(self):
        if self.MinimalSplitGain <= 0:
            self.MinimalSplitGain = 1e-30

        currentContext = []

        objectMebership = CreateMembershipTupleList(self.Dataset.Instances)
        classFeature = self.Dataset.Class

        result = DecisionTree(self.Dataset)

        filteredObjMembership = list(
            filter(lambda x: x[1] >= self.MinimalInstanceMembership, objectMebership))
        
        parentDistribution = FindDistribution(
            filteredObjMembership, self.Dataset.Model, self.Dataset.Class)
        print(f"ParentDist: {parentDistribution}")

        result.TreeRootNode = DecisionTreeNode(parentDistribution)

        self.FillNode(result.TreeRootNode,
                      filteredObjMembership, 0, currentContext)

        return result

    def FillNode(self, node, instanceTuples, level, currentContext):
        if self.StopCondition(node.Data, self.Dataset.Model, self.Dataset.Class):
            return
        if self.MaxDepth >= 0 and level >= self.MaxDepth - 1:
            return
        if sum(node.Data) <= self.MinimalObjByLeaf:
            return

        whichBetterToFind = 1
        winningSplitSelector = WinningSplitSelector(whichBetterToFind)
        currentGain = 0
        sampleFeatures = self.OnSelectingFeaturesToConsider(
            list(map(lambda attribute: attribute[0], self.Dataset.Attributes)), self.FeatureCount)

        bestFeature = None

        for feature in sampleFeatures:
            splitIterator = self.SplitIteratorProvider.GetSplitIterator(
                feature)
            if not splitIterator:
                raise Exception(f"Undefined iterator for feature {feature}")
            splitIterator.Initialize(instanceTuples)
            while splitIterator.FindNext():
                currentGain = self._distributionEvaluator(node.Data, splitIterator.CurrentDistribution)
                if currentGain >= self.MinimalSplitGain:
                    if winningSplitSelector.EvaluateThis(
                            currentGain, splitIterator, level):
                        bestFeature = self.Dataset.GetAttribute(feature)


        if bestFeature is not None and not self.Dataset.IsNominalFeature(bestFeature):
            sampleFeatures = list(filter(lambda feature: not self.Dataset.IsNominalFeature(
                feature), [self.Dataset.GetAttribute(feature) for feature in sampleFeatures]))
            featureIterator = ForwardFeatureIterator(
                self.Dataset, sampleFeatures)
            featureIterator.Add(bestFeature)
            while featureIterator.FeaturesRemain:
                bestFeature = None
                for features in featureIterator.GetFeatures():
                    candidateFeature = features[0]

                    splitIterator = self.SplitIteratorProvider.GetMultivariateSplitIterator(
                        features, self.WMin)
                    if not splitIterator:
                        raise Exception(
                            f"Undefined iterator for features {','.join(map(lambda feature: feature[0],features))}")

                    valid = splitIterator.InitializeMultivariate(
                        instanceTuples, node)

                    if not valid:
                        break

                    while splitIterator.FindNext():
                        currentGain = self._distributionEvaluator(
                            node.Data, splitIterator.CurrentDistribution)
                        if currentGain >= self.MinimalSplitGain and (currentGain - winningSplitSelector.MinStoredValue) >= self.MinimalForwardGain:
                            if winningSplitSelector.EvaluateThis(currentGain, splitIterator, level):
                                bestFeature = candidateFeature
                if not bestFeature:
                    break
                else:
                    featureIterator.Add(bestFeature)

        if winningSplitSelector.IsWinner():
            maxSelector = winningSplitSelector.WinningSelector
            node.ChildSelector = maxSelector
            node.Children = list()
            instancesPerChildNode = CreateChildrenInstances(
                instanceTuples, maxSelector, self.MinimalInstanceMembership)

            for index in range(maxSelector.ChildrenCount):
                childNode = DecisionTreeNode(winningSplitSelector.WinningDistribution[index])
                childNode.Parent = node
                node.Children.append(childNode)

                self.FillNode(
                    childNode, instancesPerChildNode[index], level + 1, currentContext)
        

        return
