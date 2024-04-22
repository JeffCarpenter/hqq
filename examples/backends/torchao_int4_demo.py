# pip install git+https://github.com/mobiusml/hqq.git;
# num_threads=12; OMP_NUM_THREADS=$num_threads CUDA_VISIBLE_DEVICES=0 ipython3 

# Tested on 4090: up to 154 tokens/sec with default compile_args
##########################################################################################################################################################
import torch, os

os.environ["TOKENIZERS_PARALLELISM"]  = "1"
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32       = True

cache_path     = '.'
model_id       = "meta-llama/Llama-2-7b-chat-hf"
compute_dtype  = torch.bfloat16 #int4 kernel only works with bfloat16
device         = 'cuda:0'

##########################################################################################################################################################
from hqq.engine.hf import HQQModelForCausalLM, AutoTokenizer
from hqq.core.quantize import *

tokenizer    = AutoTokenizer.from_pretrained(model_id, cache_dir=cache_path)
model        = HQQModelForCausalLM.from_pretrained(model_id, cache_dir=cache_path, torch_dtype=compute_dtype, attn_implementation="sdpa")
quant_config = BaseQuantizeConfig(nbits=4, group_size=64, quant_scale=False, quant_zero=False, axis=1)

#A bit better quantization results but slower
#from hqq.core.optimize import *
#Quantizer.optimize_weights = optimize_weights_proximal_slow

model.quantize_model(quant_config=quant_config, compute_dtype=compute_dtype, device=device)

#Set default backends, to compare with int4mm
if(quant_config['weight_quant_params']['axis']==0):
    HQQLinear.set_backend(HQQBackend.ATEN)
else:
    HQQLinear.set_backend(HQQBackend.PYTORCH)

##########################################################################################################################################################

#Replace HQQLinear layers matmuls to support int4 mm
from hqq.utils.patching import prepare_for_inference
prepare_for_inference(model, backend="torchao_int4")

#Import custom HF generator
from hqq.utils.generation_hf import HFGenerator

#Generate
gen = HFGenerator(model, tokenizer, do_sample=True, compile_args=None) #skips compilation: slower, but works properly
#gen = HFGenerator(model, tokenizer, do_sample=True) #compiled: much faster, but there's a bug with HF's StaticCache 

out = gen.generate("Write an essay about large language models.", max_new_tokens=1000, print_tokens=True)