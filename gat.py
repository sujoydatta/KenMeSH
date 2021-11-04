import torch
import torch.nn as nn
import torch.nn.functional as F

from dgl.nn.pytorch import GATConv


class GAT(nn.Module):
    def __init__(self,
                 device,
                 g,
                 num_layers,
                 in_node_feats,
                 hidden_gat_size,
                 num_classes,
                 heads,
                 activation=F.elu,
                 feat_drop=0,
                 attn_drop=0,
                 negative_slope=0.2,
                 residual=False):
        super(GAT, self).__init__()
        self.g = g.to(device)
        self.num_layers = num_layers
        self.gat_layers = nn.ModuleList()
        self.activation = activation
        # input projection (no residual)
        self.gat_layers.append(GATConv(
            in_node_feats, hidden_gat_size, heads[0],
            feat_drop, attn_drop, negative_slope, False, self.activation, True))
        # hidden layers
        for l in range(1, num_layers):
            # due to multi-head, the in_dim = num_hidden * num_heads
            self.gat_layers.append(GATConv(
                hidden_gat_size * heads[l-1], hidden_gat_size, heads[l],
                feat_drop, attn_drop, negative_slope, residual, self.activation, True))
        # output projection
        self.gat_layers.append(GATConv(
            hidden_gat_size * heads[-2], num_classes, heads[-1],
            feat_drop, attn_drop, negative_slope, residual, None, True))

    def forward(self, inputs):
        h = inputs
        # print('g device', self.g.device)
        for l in range(self.num_layers):
            h = self.gat_layers[l](self.g, h).flatten(1)
        # output projection
        logits = self.gat_layers[-1](self.g, h).mean(1)
        # print('logits', logits.shape)
        return logits

