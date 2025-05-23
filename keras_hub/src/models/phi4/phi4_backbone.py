import keras

from keras_hub.src.api_export import keras_hub_export
from keras_hub.src.layers.modeling.reversible_embedding import (
    ReversibleEmbedding,
)
from keras_hub.src.models.backbone import Backbone
from keras_hub.src.models.phi4.phi4_decoder import Phi4Decoder
from keras_hub.src.models.phi4.phi4_layernorm import Phi4LayerNorm


def _phi4_kernel_initializer(stddev=0.02):
    return keras.initializers.RandomNormal(stddev=stddev)


@keras_hub_export("keras_hub.models.Phi4Backbone")
class Phi4Backbone(Backbone):
    """Phi-4 core network with hyperparameters.

    This network implements a Transformer-based decoder network,
    Phi-4, as described in ["Phi-4 Technical Report"](https://arxiv.org/pdf/2412.08905).
    It includes the embedding lookups and transformer layers.

    The default constructor gives a fully customizable, randomly initialized
    phi-4 model with any number of layers, heads, and embedding
    dimensions. To load preset architectures and weights, use the `from_preset`
    constructor.

    Args:
        vocabulary_size (int): The size of the token vocabulary. Defaults to
            `100_352`.
        num_layers (int): The number of transformer layers. Defaults to `40`.
        hidden_dim (int): The size of the embeddings and the hidden states of
            the transformer layers. Defaults to `5120`.
        intermediate_dim (int): The output dimension of the first Dense layer in
            a three-layer feedforward network for each transformer. Defaults to
            `17_920`.
        num_query_heads (int): The number of query attention heads for each
            transformer layer. Defaults to `40`.
        num_key_value_heads (int): The number of key and value attention heads
            for each transformer layer. Defaults to `10`.
        layer_norm_epsilon (float, optional): Epsilon for the RMS layernorm
            layers in the transformer decoder. Defaults to `1e-5`.
        dropout: (float, optional): Dropout probability for the Transformer
            decoder. Defaults to `0.0`.
        max_sequence_length (int, optional): The maximum sequence length
            that this model might ever be used with. Defaults to `16_384`.
        pretraining_sequence_length (int, optional): The maximum sequence length
            that the model was pretrained with. Defaults to `16_384`.
        rope_max_wavelength (int, optional): The maximum angular wavelength of
            the sine/cosine curves, for rotary embeddings. Defaults to
            `250_000`.
        rope_scaling_type (str, optional): The type of the rope scaling. Can be
            either `None` or `"su"`. `None` is for no rope scaling, `"su"` is
            for SuScaled rope, `"su"` is used when `max_sequence_length` is
            larger than `original_max_sequence_length`. Defaults to `None`.
        rope_scaling_short_factor List[float]: List of factors used to adjust
            rope frequencies when the `rope_scaling_type` is `"su"`. List must
            be of length `hidden_dim//num_query_heads//2`. It is used when
            `sequence_length` is smaller than `original_max_sequence_length`.
            Defaults to `None`.
        rope_scaling_long_factor List[float]: List of factors used to adjust
            rope frequencies when the `rope_scaling_type` is `"su"`. List must
            be of length `hidden_dim//num_query_heads//2`. It is used when
            `sequence_length` is larger than `original_max_sequence_length`.
            Defaults to `None`.
        dtype: string or `keras.mixed_precision.DTypePolicy`. The dtype to use
            for model computations and weights. Note that some computations,
            such as softmax and layer normalization, will always be done at
            float32 precision regardless of dtype.

    Examples:

    ```python
    input_data = {
        "token_ids": np.ones(shape=(1, 12), dtype="int32"),
        "padding_mask": np.array([[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0]]),
    }

    # Pretrained Phi4 decoder.
    model = keras_hub.models.Phi4Backbone.from_preset(
        "phi4_mini_4k_instruct_en"
    )
    model(input_data)

    # Randomly initialized Phi4 decoder with custom config.
    model = keras_hub.models.Phi4Backbone(
        vocabulary_size=10,
        num_layers=2,
        hidden_dim=512,
        intermediate_dim=1024,
        num_query_heads=32,
        num_key_value_heads=8,
        layer_norm_epsilon=1e-6,
        dtype="bfloat16"
    )
    model(input_data)
    ```

    References:
    - [Phi-4 Original Implementation](https://huggingface.co/microsoft/phi-4/blob/main/config.json)
    """

    def __init__(
        self,
        vocabulary_size=100_352,
        num_layers=40,
        hidden_dim=5120,
        intermediate_dim=17_920,
        num_query_heads=40,
        num_key_value_heads=10,
        layer_norm_epsilon=1e-5,
        dropout=0.0,
        max_sequence_length=16_384,
        pretraining_sequence_length=16_384,
        rope_max_wavelength=250_000,
        rope_scaling_type=None,
        rope_scaling_short_factor=None,
        rope_scaling_long_factor=None,
        dtype=None,
        **kwargs,
    ):
        # === Layers ===
        self.token_embedding = ReversibleEmbedding(
            input_dim=vocabulary_size,
            output_dim=hidden_dim,
            tie_weights=False,
            embeddings_initializer=_phi4_kernel_initializer(stddev=0.01),
            dtype=dtype,
            name="token_embedding",
        )
        self.transformer_layers = []
        for i in range(num_layers):
            layer = Phi4Decoder(
                hidden_dim=hidden_dim,
                intermediate_dim=intermediate_dim,
                num_query_heads=num_query_heads,
                num_key_value_heads=num_key_value_heads,
                rope_max_wavelength=rope_max_wavelength,
                layer_norm_epsilon=layer_norm_epsilon,
                activation="silu",
                kernel_initializer=_phi4_kernel_initializer(stddev=0.02),
                dropout=dropout,
                max_sequence_length=max_sequence_length,
                pretraining_sequence_length=pretraining_sequence_length,
                rope_scaling_type=rope_scaling_type,
                rope_scaling_short_factor=rope_scaling_short_factor,
                rope_scaling_long_factor=rope_scaling_long_factor,
                dtype=dtype,
                name=f"transformer_layer_{i}",
            )
            self.transformer_layers.append(layer)
        self.layer_norm = Phi4LayerNorm(
            epsilon=layer_norm_epsilon,
            dtype=dtype,
            name="sequence_output_layernorm",
        )

        # === Functional Model ===
        token_id_input = keras.Input(
            shape=(None,), dtype="int32", name="token_ids"
        )
        padding_mask_input = keras.Input(
            shape=(None,), dtype="int32", name="padding_mask"
        )
        x = self.token_embedding(token_id_input)
        for transformer_layer in self.transformer_layers:
            x = transformer_layer(x, decoder_padding_mask=padding_mask_input)
        sequence_output = self.layer_norm(x)
        super().__init__(
            inputs={
                "token_ids": token_id_input,
                "padding_mask": padding_mask_input,
            },
            outputs=sequence_output,
            dtype=dtype,
            **kwargs,
        )

        # === Config ===
        self.vocabulary_size = vocabulary_size
        self.num_layers = num_layers
        self.num_query_heads = num_query_heads
        self.num_key_value_heads = num_key_value_heads
        self.hidden_dim = hidden_dim
        self.intermediate_dim = intermediate_dim
        self.rope_scaling_type = rope_scaling_type
        self.layer_norm_epsilon = layer_norm_epsilon
        self.dropout = dropout
        self.max_sequence_length = max_sequence_length
        self.pretraining_sequence_length = pretraining_sequence_length
        self.rope_max_wavelength = rope_max_wavelength
        self.rope_scaling_type = rope_scaling_type
        self.rope_scaling_short_factor = rope_scaling_short_factor
        self.rope_scaling_long_factor = rope_scaling_long_factor

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "vocabulary_size": self.vocabulary_size,
                "num_layers": self.num_layers,
                "num_query_heads": self.num_query_heads,
                "hidden_dim": self.hidden_dim,
                "intermediate_dim": self.intermediate_dim,
                "num_key_value_heads": self.num_key_value_heads,
                "layer_norm_epsilon": self.layer_norm_epsilon,
                "dropout": self.dropout,
                "max_sequence_length": self.max_sequence_length,
                "pretraining_sequence_length": self.pretraining_sequence_length,
                "rope_max_wavelength": self.rope_max_wavelength,
                "rope_scaling_type": self.rope_scaling_type,
                "rope_scaling_short_factor": self.rope_scaling_short_factor,
                "rope_scaling_long_factor": self.rope_scaling_long_factor,
            }
        )
        return config
