"""
Created on Wed Apr 26 14:36:27 2017

@author: yajun
"""

import obspy
from obspy import UTCDateTime
from obspy.signal.trigger import trigger_onset
import matplotlib.pyplot as plt
from obspy.signal.trigger import plot_trigger, recursive_sta_lta

plt.style.use('seaborn-darkgrid')


def highpass_filter_waveform(trace, freq):
    trace.detrend('linear')
    trace.taper(0.1)
    trace.filter('highpass', freq=freq, corners=4, zerophase=False)
    trace.detrend('linear')
    trace.taper(0.1)


def check_arrival_time(P_arrivals, waveform_start_time,
                       origin_time, df):
    """
    Check if the arrival time is after the origin time.
    """
    P_pick_true = ()
    for i_arrival in range(len(P_arrivals)):
        time_pick = waveform_start_time + float(P_arrivals[i_arrival][0] / df)
        if time_pick > origin_time:
            P_pick_true = (time_pick, P_arrivals[i_arrival][0])
            break

    return P_pick_true


def pick_arrival(trace, nsta_seconds, nlta_seconds, df,
                 origin_time, pick_threshold,
                 plot_flag='off'):
    """
    P wave arrival is picked using a recursive sta/lta algorithm.
    """
    cft = recursive_sta_lta(trace,
                            int(nsta_seconds * df),
                            int(nlta_seconds * df))
    P_arrivals = trigger_onset(cft, pick_threshold, 0.5)
    if plot_flag == 'on':
        plot_trigger(trace, cft, pick_threshold, 0.5, show=True)

    P_pick_true = check_arrival_time(P_arrivals, trace.stats.starttime, origin_time, df)

    return P_pick_true


def P_wave_onset_and_SNR(stream, origin_time,
                         pre_filter=False, pick_filter=True,
                         tigger_threshold=150, SNR_threshold=150,
                         nsta_seconds=0.05, nlta_seconds=20,
                         SNR_plot_flag='off', tigger_plot_flag='off'):
    """
    Pick P wave (seimic wave that arrives first) onset time 
    from the vertical component using a recursive STA/LTA 
    method (Withers et al., 1998). Signal-to-noise ratio 
    is determined from the STA/LTA characteristic function.

    Stream: obspy stream containing multiple seismogram traces.
    origin_time: earthquake origin time in UTCDateTime format.

    Set pre_filter = True to first apply a highpass filter 
    (> 0.075 Hz) to the stream. 
    Set pick_filter = True to apply a highpass filter (> 1 Hz)
    to pick the onset. This should improve the onset accuracy.

    Return P_onset, a dictionary: 
    {station name: ((arrival in UTCDateTime, arrival in samples since start_time), 
                    boolean indicating whether SNR > SNR_threshold)}       
    """
    P_onset = {}
    stream_vertical = stream.select(channel='*Z*')
    for trace in stream_vertical:
        P_pick_SNR = ()  # Check SNR using P wave arrival pick for the unfiltered waveform
        P_pick_hfreq = ()  # P wave arrival pick for highpass filtered (> 1 Hz) waveform
        P_pick = ()  # Picked P arrival. The same as P_pick_SNR when pick_filter = False
        df = trace.stats.sampling_rate

        if pre_filter:
            highpass_filter_waveform(trace, 0.075)

        # The main objective is to calculate SNR. But can be used to pick arrival time
        # when pick_filter = False.
        P_pick_SNR = pick_arrival(trace, nsta_seconds,
                                  nlta_seconds, df,
                                  origin_time, SNR_threshold,
                                  plot_flag=SNR_plot_flag)

        if not pick_filter:
            P_pick = P_pick_SNR
        else:
            trace_copy = trace.copy()
            highpass_filter_waveform(trace_copy, 1)

            # Pick arrival again using highpassed waveform
            P_pick_hfreq = pick_arrival(trace_copy, nsta_seconds,
                                        nlta_seconds, df,
                                        origin_time, tigger_threshold,
                                        plot_flag=tigger_plot_flag)

            # Check consistency between P_pick_hfreq and P_pick_SNR
            # Use P_pick_hfreq when the two values are within 0.5 s.
            if len(P_pick_hfreq) != 0:
                if (len(P_pick_SNR) != 0):
                    if abs(P_pick_hfreq[0] - P_pick_SNR[0]) < 0.5:
                        P_pick = P_pick_hfreq
                    else:
                        P_pick = ()
                else:
                    P_pick = P_pick_hfreq

                    # Output
        if len(P_pick) != 0:
            P_onset.update({trace.stats.station:
                                (P_pick, len(P_pick_SNR) != 0)})

    return P_onset
