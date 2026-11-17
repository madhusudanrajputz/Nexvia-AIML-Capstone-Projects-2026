
import torch
from torch import nn
from torch_geometric.nn import SAGEConv

class FraudGraphSAGE(nn.Module):
    def __init__(
        self,
        node_dim=8,
        transaction_dim=6,
        hidden_dim=32,
        dropout=0.20
    ):
        super().__init__()

        self.node_input = nn.Sequential(
            nn.Linear(node_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU()
        )

        self.conv1 = SAGEConv(hidden_dim, hidden_dim)
        self.conv2 = SAGEConv(hidden_dim, hidden_dim)

        self.transaction_encoder = nn.Sequential(
            nn.Linear(transaction_dim, 16),
            nn.ReLU()
        )

        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 3 + 16, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )

    def forward(self, batch):
        x = self.node_input(batch.x)
        x = self.conv1(x, batch.edge_index).relu()
        x = self.conv2(x, batch.edge_index).relu()

        source = x[batch.source_index.view(-1)]
        destination = x[batch.destination_index.view(-1)]

        transaction = self.transaction_encoder(
            batch.transaction_features
        )

        combined = torch.cat(
            [
                source,
                destination,
                torch.abs(source - destination),
                transaction
            ],
            dim=1
        )

        return self.classifier(combined).view(-1)
