import os
from unittest.mock import patch

import pytest
from keras import ops

from keras_hub.src.models.phi4.phi4_backbone import Phi4Backbone
from keras_hub.src.models.phi4.phi4_causal_lm import Phi4CausalLM
from keras_hub.src.models.phi4.phi4_causal_lm_preprocessor import (
    Phi4CausalLMPreprocessor,
)
from keras_hub.src.models.phi4.phi4_tokenizer import Phi4Tokenizer
from keras_hub.src.tests.test_case import TestCase


class Phi4CausalLMTest(TestCase):
    def setUp(self):
        self.preprocessor = Phi4CausalLMPreprocessor(
            Phi4Tokenizer(
                # Generated using create_phi4_test_proto.py
                proto=os.path.join(
                    self.get_test_data_dir(), "phi4_test_vocab.spm"
                )
            ),
            sequence_length=12,
        )
        self.vocab_size = self.preprocessor.tokenizer.vocabulary_size()
        self.backbone = Phi4Backbone(
            vocabulary_size=self.vocab_size,
            num_layers=2,
            num_query_heads=4,
            num_key_value_heads=2,
            hidden_dim=8,
            intermediate_dim=16,
        )
        self.init_kwargs = {
            "preprocessor": self.preprocessor,
            "backbone": self.backbone,
        }
        self.train_data = (["the quick brown fox", "the earth is round"],)
        self.input_data = self.preprocessor(*self.train_data)[0]

    def test_causal_lm_basics(self):
        self.run_task_test(
            cls=Phi4CausalLM,
            init_kwargs=self.init_kwargs,
            train_data=self.train_data,
            expected_output_shape=(2, 12, self.vocab_size),
        )

    def test_generate(self):
        causal_lm = Phi4CausalLM(**self.init_kwargs)
        # String input.
        prompt = "the fox"
        output = causal_lm.generate(prompt)
        self.assertTrue(prompt in output)
        # Int tensor input.
        prompt_ids = self.preprocessor.generate_preprocess([prompt])
        causal_lm.preprocessor = None
        outputs = causal_lm.generate(prompt_ids, stop_token_ids=None)
        # Assert prompt is in output in token id space.
        self.assertAllEqual(
            outputs["token_ids"][:, :5],
            prompt_ids["token_ids"][:, :5],
        )
        self.assertAllEqual(
            outputs["padding_mask"][:, :5],
            prompt_ids["padding_mask"][:, :5],
        )

    def test_early_stopping(self):
        causal_lm = Phi4CausalLM(**self.init_kwargs)
        call_with_cache = causal_lm.call_with_cache

        def wrapper(*args, **kwargs):
            """Modify output logits to always favor end_token_id"""
            logits, hidden_states, cache = call_with_cache(*args, **kwargs)
            index = self.preprocessor.tokenizer.end_token_id
            update = ops.ones_like(logits)[:, :, index] * 1.0e9
            update = ops.expand_dims(update, axis=-1)
            logits = ops.slice_update(logits, (0, 0, index), update)
            return logits, hidden_states, cache

        with patch.object(causal_lm, "call_with_cache", wraps=wrapper):
            prompt = ["the fox", "the earth"]
            output = causal_lm.generate(prompt)
            # We should immediately abort and output the prompt.
            self.assertEqual(prompt, output)

    def test_generate_compilation(self):
        causal_lm = Phi4CausalLM(**self.init_kwargs)
        # Assert we do not recompile with successive calls.
        causal_lm.generate("the fox")
        first_fn = causal_lm.generate_function
        causal_lm.generate("the fox")
        second_fn = causal_lm.generate_function
        self.assertEqual(first_fn, second_fn)
        # Assert we do recompile after compile is called.
        causal_lm.compile(sampler="greedy")
        self.assertIsNone(causal_lm.generate_function)

    # @pytest.mark.large
    def test_saved_model(self):
        self.run_model_saving_test(
            cls=Phi4CausalLM,
            init_kwargs=self.init_kwargs,
            input_data=self.input_data,
        )

    @pytest.mark.extra_large
    def test_all_presets(self):
        for preset in Phi4CausalLM.presets:
            self.run_preset_test(
                cls=Phi4CausalLM,
                preset=preset,
                input_data=self.input_data,
            )
