import argparse
import os
import pathlib
import matplotlib.pylab as plt
import pandas as pd
alphabet = 'ARNDCQEGHILKMFPSTWYV'
def plot_w(df_ori, sequence, pop=False, annotate=False, base=0, png_name='undefined.png', score_max_abs=None):
    
    df = df_ori.copy()
    
    if pop:
        df.pop(0)
    
    plt.figure(figsize=(len(sequence) / 4, 20 / 4))
    
    if score_max_abs is not None:
        pcm = plt.imshow(df, cmap='bwr_r', vmax=score_max_abs, vmin=-score_max_abs)
    else:
        pcm = plt.imshow(df, cmap='bwr_r')
    
    al_a = [x[0] for x in df.index.values.tolist()]
    
    alphabet = ''.join(al_a)
    
    if len(sequence) <= 20:
        s = 2
    elif len(sequence) <= 100:
        s = 5
    else:
        s = 10
    
    x_ax = [0]
    x_ax += [x for x in range(len(sequence) + 1) if x % s == 0 and x != 0]
    plt.xticks([x - 1 for x in x_ax], [base + x for x in x_ax])
    plt.yticks(range(len(alphabet)), list(alphabet))
    plt.xlabel('Positions')
    plt.ylabel('Amino Acid')
    plt.grid(False)
    
    plt.colorbar(pcm)
    
    if annotate:
        for a in range(len(alphabet)):
            for pos in range(len(sequence)):
                if al_a[a] == sequence[pos]:
                    plt.text(pos, a, al_a[a], ha="center", va="center", color="k")
    
    if png_name:
        png_name = pathlib.Path(png_name).resolve()
        os.makedirs(png_name.parent, exist_ok=True)
        plt.savefig(png_name)
    
def plot_in_segment(df, sequence, n, label, save_dir, score_max_abs):
    
    df_1 = df.copy()
    
    
    
    for i in range(df.shape[1]):
        i_ = int(i)
        if i % n == 0:
            plot_w(df_1.iloc[:, i_:i_ + n], sequence[i_:i_ + n], annotate=True, base=i_,
                   png_name=f"{save_dir}/{label}_{i_}-{i_ + n}.png", score_max_abs=score_max_abs)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize Deep Mutation Scan results of ESM-1v for a sequence.")
    parser.add_argument('--sequence', dest='sequence', help='sequence for scan', required=True, type=str)
    parser.add_argument('--instance', dest='instance', help='instance for pdb', required=True, type=str)
    parser.add_argument('--mutant_col', dest='mutant_col', help='mutant_col for DMS', default="mutations", type=str)
    parser.add_argument('--models', dest='models', help='models path used for ESM-1v', type=str, nargs='+',
                        default=[
                            '/mnt/db/esm/esm1v_t33_650M_UR90S_1.pt',
                            '/mnt/db/esm/esm1v_t33_650M_UR90S_2.pt',
                            '/mnt/db/esm/esm1v_t33_650M_UR90S_3.pt',
                            '/mnt/db/esm/esm1v_t33_650M_UR90S_4.pt',
                            '/mnt/db/esm/esm1v_t33_650M_UR90S_5.pt',
                        ])
    parser.add_argument('--model_names', dest='model_names', action="store", type=str, nargs='+',
                        default=['esm-1v_1', 'esm-1v_2', 'esm-1v_3', 'esm-1v_4', 'esm-1v_5'],
                        help="method names used for generating mut tables")
    parser.add_argument('--esm_dms_csv', dest='esm_dms_csv', help='esm_dms_csv', required=True,
                        type=str)
    parser.add_argument('--save_dir', dest='save_dir', action="store", type=str, default=".",
                        help="Path to save results")
    args_dict = vars(parser.parse_args())
    
    sequence = args_dict['sequence']
    instance = args_dict['instance']
    models = args_dict['models']
    model_names = args_dict['model_names']
    esm_dms_csv = args_dict['esm_dms_csv']
    mutant_col = args_dict['mutant_col']
    save_dir = args_dict['save_dir']
    
    assert len(sequence) > 0
    assert instance is not None and instance != ''
    assert os.path.exists(esm_dms_csv)
    assert len(model_names) == len(models)
    os.makedirs(save_dir, exist_ok=True)
    df_dms = pd.read_csv(esm_dms_csv)
    for col in df_dms.columns:
        if col == mutant_col:
            break
        df_dms.drop(columns=[col], inplace=True)
    if model_names[0] not in df_dms.columns:
        df_dms.rename(columns={model: model_name for model, model_name in zip(models, model_names)}, inplace=True)
    df_dms['wt_aa'] = df_dms[mutant_col].str.split().str[0].str[0]
    df_dms['mut_aa'] = df_dms[mutant_col].str.split().str[0].str[-1]
    df_dms['pos'] = df_dms[mutant_col].str.split().str[0].str[1:-1].astype(int)
    for model_name in model_names:
        df_this_model = df_dms[[model_name, 'wt_aa', 'pos', 'mut_aa']]
        df_this_model_ = pd.DataFrame(columns=[x for x in alphabet])
        print(f'Processing model prediction: {model_name} ...')
        
        for wt, pos, mut, sc in zip(df_this_model['wt_aa'], df_this_model['pos'], df_this_model['mut_aa'],
                                    df_this_model[model_name]):
            
            
            df_this_model_.loc[pos, mut] = sc
        
        df_this_model_.fillna(0, inplace=True)
        
        
        
        
        df_this_model_t = df_this_model_[[x for x in alphabet]].transpose()
        
        sc_minima = min(df_this_model_t.min())
        sc_maxima = max(df_this_model_t.max())
        sc_max_abs = max(abs(sc_minima), abs(sc_maxima))
        print(f'scores minima: {-sc_max_abs}')
        print(f'scores maxima: {sc_max_abs}')
        
        
        print(f'color scale: {-sc_max_abs}:{sc_max_abs}')
        
        plot_w(df_ori=df_this_model_t, sequence=sequence, annotate=True, pop=False,
               png_name=f'{save_dir}/{instance}_{model_name}_full_prediction.png', score_max_abs=sc_max_abs)
        
        plot_in_segment(
            df=df_this_model_t,
            sequence=sequence,
            n=100,
            label=f'{instance}_{model_name}',
            save_dir=save_dir,
            score_max_abs=sc_max_abs)
        
        mut_list = []
        for idx in range(1, len(sequence) + 1):
            wt_aa = sequence[idx - 1]
            df_this_model_screen = df_this_model_t[df_this_model_t.loc[:, idx] > 0].index.tolist()
            if len(df_this_model_screen) > 0:
                for mut in df_this_model_screen:
                    
                    mut_list.append(f'{wt_aa}{idx}{mut}')
        with open(f'{save_dir}/mutlist_{instance}_{model_name}_dms.txt', 'w') as dms_mutlist_fh:
            dms_mutlist_fh.write('\n'.join(mut_list))
        
        df_this_model_t.to_csv(f'{save_dir}/{instance}_{model_name}_dms_mtx.csv')