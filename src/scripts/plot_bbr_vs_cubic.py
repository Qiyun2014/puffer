#!/usr/bin/env python3

import sys
import yaml
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from helpers import (
    connect_to_postgres, retrieve_expt_config, ssim_index_to_db)
from collect_data import collect_video_data, collect_buffer_data, VIDEO_DURATION


# cache of Postgres data: experiment 'id' -> json 'data' of the experiment
expt_id_cache = {}


def plot_ssim_cdf(data, args):
    fig, ax = plt.subplots()

    x_min = 0
    x_max = 25
    num_bins = 100
    for cc in data:
        counts, bin_edges = np.histogram(data[cc], bins=num_bins,
                                         range=(x_min, x_max))

        x = bin_edges
        y = np.cumsum(counts) / len(data[cc])
        y = np.insert(y, 0, 0)  # prepend 0

        ax.plot(x, y, label=cc)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0, 1)
    ax.legend()
    ax.grid()

    title = '[{}, {}] (UTC)'.format(args.time_start, args.time_end)
    ax.set_title(title)
    ax.set_xlabel('SSIM (dB)')
    ax.set_ylabel('CDF')

    figname = 'bbr_cubic_ssim_cdf.png'
    fig.savefig(figname, dpi=150, bbox_inches='tight')
    sys.stderr.write('Saved plot to {}\n'.format(figname))


def plot_ssim_var_cdf(data, args):
    fig, ax = plt.subplots()

    x_min = 0
    x_max = 4
    num_bins = 100
    for cc in data:
        counts, bin_edges = np.histogram(data[cc], bins=num_bins,
                                         range=(x_min, x_max))

        x = bin_edges
        y = np.cumsum(counts) / len(data[cc])
        y = np.insert(y, 0, 0)  # prepend 0

        ax.plot(x, y, label=cc)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0, 1)
    ax.legend()
    ax.grid()

    title = '[{}, {}] (UTC)'.format(args.time_start, args.time_end)
    ax.set_title(title)
    ax.set_xlabel('Absolute SSIM variation')
    ax.set_ylabel('CDF')

    figname = 'bbr_cubic_ssim_var_cdf.png'
    fig.savefig(figname, dpi=150, bbox_inches='tight')
    sys.stderr.write('Saved plot to {}\n'.format(figname))


def plot_ssim(d, postgres_cursor, args):
    ssim_by_cc = {}
    ssim_var_by_cc = {}

    for session in d:
        expt_id = session[3]
        expt_config = retrieve_expt_config(expt_id, expt_id_cache,
                                           postgres_cursor)
        cc = expt_config['cc']
        if cc not in ssim_by_cc:
            ssim_by_cc[cc] = []
            ssim_var_by_cc[cc] = []

        for video_ts in d[session]:
            dsv = d[session][video_ts]

            # append SSIM
            curr_ssim_index = dsv['ssim_index']
            if curr_ssim_index == 1:
                continue

            curr_ssim_db = ssim_index_to_db(curr_ssim_index)
            ssim_by_cc[cc].append(curr_ssim_db)

            # append SSIM variation
            prev_ts = video_ts - VIDEO_DURATION
            if prev_ts not in d[session]:
                continue

            prev_ssim_index = d[session][prev_ts]['ssim_index']
            if prev_ssim_index == 1:
                continue

            prev_ssim_db = ssim_index_to_db(prev_ssim_index)
            ssim_diff = abs(curr_ssim_db - prev_ssim_db)
            ssim_var_by_cc[cc].append(ssim_diff)

    # plot CDF of SSIM
    plot_ssim_cdf(ssim_by_cc, args)

    # plot CDF of SSIM variation
    plot_ssim_var_cdf(ssim_var_by_cc, args)


def plot_rebuf_rate_cdf(data, args):
    fig, ax = plt.subplots()

    x_min = None
    x_max = None
    for cc in data:
        data_min = np.min(data[cc])
        if x_min is None or data_min < x_min:
            x_min = data_min

        data_max = np.max(data[cc])
        if x_max is None or data_max > x_max:
            x_max = data_max

    num_bins = 100
    for cc in data:
        counts, bin_edges = np.histogram(data[cc], bins=num_bins,
                                         range=(x_min, x_max))

        x = bin_edges
        y = np.cumsum(counts) / len(data[cc])
        y = np.insert(y, 0, 0)  # prepend 0

        ax.plot(x, y, label=cc)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0, 1)
    ax.legend()
    ax.grid()

    title = '[{}, {}] (UTC)'.format(args.time_start, args.time_end)
    ax.set_title(title)
    ax.set_xlabel('Rebuffer rate (%)')
    ax.set_ylabel('CDF')

    figname = 'bbr_cubic_rebuf_rate_cdf.png'
    fig.savefig(figname, dpi=150, bbox_inches='tight')
    sys.stderr.write('Saved plot to {}\n'.format(figname))


def plot_rebuf_rate(d, postgres_cursor, args):
    rebuf_rate_by_cc = {}

    for session in d:
        expt_id = session[3]
        expt_config = retrieve_expt_config(expt_id, expt_id_cache,
                                           postgres_cursor)
        cc = expt_config['cc']
        if cc not in rebuf_rate_by_cc:
            rebuf_rate_by_cc[cc] = []

        rebuf_rate_by_cc[cc].append(100 * d[session]['rebuf'] / d[session]['play'])

    # plot CDF of rebuffer rate
    plot_rebuf_rate_cdf(rebuf_rate_by_cc, args)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('yaml_settings')
    parser.add_argument('--from', dest='time_start',
                        help='datetime in UTC conforming to RFC3339')
    parser.add_argument('--to', dest='time_end',
                        help='datetime in UTC conforming to RFC3339')
    args = parser.parse_args()

    yaml_settings_path = args.yaml_settings
    with open(yaml_settings_path, 'r') as fh:
        yaml_settings = yaml.safe_load(fh)

    video_data = collect_video_data(yaml_settings_path,
                                    args.time_start, args.time_end, None)

    buffer_data = collect_buffer_data(yaml_settings_path,
                                      args.time_start, args.time_end)

    # create a client connected to Postgres
    postgres_client = connect_to_postgres(yaml_settings)
    postgres_cursor = postgres_client.cursor()

    # plot SSIM and its variation
    plot_ssim(video_data, postgres_cursor, args)

    # plot rebuffer rate
    plot_rebuf_rate(buffer_data, postgres_cursor, args)

    postgres_cursor.close()


if __name__ == '__main__':
    main()
