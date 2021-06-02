# Availability in SDTN

This is an experiment addressing availability issues in Software-Defined Tactical Networks.
The availability of services in those networks can be affected by disruptive network scenarios that can be caused by interference, barriers or the mobility of nodes.

We developed an approach to reduce the probability that such situations of unavailability occur.
To test our approach we used Mininet-Wifi to emulate a wireless network and simulate a mobility scenario.
This scenario includes two nodes (1, 2) with wireless interfaces and an access point (AP) that is also a SDN switch and has a wired link to a SDN controller.
The scenario also includes a permanent data flow from node 1 to node 2.
At first, the nodes 1 and 2 are connected to the SDN controller through the access point.
Then the nodes are being disrupted from the access point.
This also disrupts the data flow between them because the two nodes have no connection to each other anymore.

The central part of the approach towards improving the availability in this scenario is a script that can be run in each of the data forwarding nodes.
The script enables the nodes to switch their wireless interfaces from managed mode to ad-hoc mode whenever they are disrupted from the infrastructure.
In ad-hoc mode the nodes use OLSR to establish a communication channel to prevent the data flow from being disrupted.

## Getting Started
The experiment is based on the Mininet-Wifi framework.
We recommend the usage of the Mininet-Wifi VM to test this experimental setup.

You can find the download link for the VM and the instructions how to use it in the Mininet-Wifi [Github repository](https://github.com/intrig-unicamp/mininet-wifi#pre-configured-virtual-machine).
Since our project uses OLSR as a central element of the approach you need to make sure that your version of Mininet-Wifi or the version that is pre-installed on the VM has OLSR installed.
Otherwise, please install OLSR or re-install Mininet-Wifi with the OLSR option selected for the installation.
You can also find instructions for that in the documentation of Mininet-Wifi.

If you have not used the scripts of this project before we recommend reading the following sections.
There, you will find important information about how to set everything up initially.

_**Note:** Additional important information for the usage of this project can be found in the comments of the python scripts, especially in the files `sdn_topology.py` and `flexible_sdn.py`.
We strongly recommend looking into the code of those files before using them._

### Dependencies
This project has been written in Python and needs Python 3.7 or higher.
Besides the Mininet-Wifi framework the experiment requires the following Python libraries:

 - numpy
 - pandas
 - matplotlib
 - pyshark

Additionally, Mininet-Wifi has to be modified for this experiment to work properly.
The modification is explained in detail in the next [section](#how-to-modify-mininet-wifi-to-work-with-this-experiment) 
The further usage of this experiment is explained after that in the section: [How to use the experiment setup](#how-to-use-the-experiment-setup)

Furthermore, the experiment uses `D-ITG` to generate a data flow.
Documentation and installation instructions can be found here:
[http://traffic.comics.unina.it/software/ITG/index.php](http://traffic.comics.unina.it/software/ITG/index.php)

```shell
install d-itg: $ sudo apt install d-itg
```

```shell
git clone https://github.com/KimiNewt/pyshark.git
cd pyshark/src
python setup.py install
```

### How to modify Mininet-Wifi to work with this experiment
_**Note:** If you don't care about the explanation why this modification is necessary and just want to know how to apply it then you can jump to [How to apply the modification](#how-to-apply-the-modification)._

Mininet-Wifi includes a feature that conflicts with our approach.
The framework has a mechanism implemented to automize handovers and reconnections to access points when a mobility pattern is replayed.
This can cause distortions in the result of our experiment because the framework does not recognize when we let a node switch from managed mode to ad-hoc mode manually.
If the node disconnects from an access point and switches to ad-hoc mode during the experiment the framework will automatically search for access points in range and try to reconnect to them.
This blocks the primary network interface which should be used for the data flow in our experiment.
The data flow will then be disrupted due to the framework executing the automated reconnection trials.

In our experiment the disconnections from access points as well as reconnections and handovers are central part of the approach.
We want to be able to precisely control when disconnections, reconnections or handovers will be executed, so we have to deactivate this feature.
Sadly, this is not possible without manipulating the code of Mininet-Wifi.
Initializing the Mininet-Wifi with the options `autoAssociation=False, allAutoAssociation=False` did not fix this problem although the documentation made us believe that it should (Maybe this is a bug? :thinking:).


#### How to apply the Modification
For the fix you just need to comment out one line where the function is called that causes the disturbance.
The line that has to be removed or commented out can be found under the following link:

[https://github.com/intrig-unicamp/mininet-wifi/blob/d94975f9aebba1805d403a4a1be25867cf147aef/mn_wifi/replaying.py#L80](https://github.com/intrig-unicamp/mininet-wifi/blob/d94975f9aebba1805d403a4a1be25867cf147aef/mn_wifi/replaying.py#L80)

It is inside the function `mn_wifi.replaying.ReplayingMobility.mobility`

To fix the above mentioned issue just comment out the line `ConfigMobLinks()` in the same way as in the following example:
```python
class ReplayingMobility(Mobility):
    ...

    def mobility(self, nodes):
        ...
        
        while self.thread_._keep_alive:
            time_ = time() - currentTime
            if len(nodes) == 0:
                break
            for node in nodes:
                if hasattr(node, 'p'):
                    calc_pos(node, time_)
                    if len(node.p) == 0:
                        nodes.remove(node)
                    # ConfigMobLinks()
                    if self.net.draw:
                        node.update_2d()
            if self.net.draw:
                PlotGraph.pause()
```

After that re-install the modified Mininet-Wifi using the original installation script.
Without the re-installation the fix will not be applied to the version which is used by python.

```shell
re-install Mininet-Wifi: $ cd mininet-wifi
re-install Mininet-Wifi: $ sudo util/install.sh -Wlnfv
OLSR: $ sudo util/install.sh -O
```

To undo this modification just undo the comment in the mentioned line and reinstall Mininet-Wifi again.


## How to use the experiment setup
We assume that you have completed the following steps at this point:

 - Modified Mininet-Wifi to prevent it from disturbing the experiment
 - Installed the modified version of Mininet-Wifi (preferably in the Mininet-Wifi VM)
 - Installed OLSR
 - Installed all required Python libraries
 - Installed D-ITG

If you did not complete all of the above setup steps then please refer to the previous section: [Setup](#setup).
If you have set everything up then you can continue with the next steps.

In the standard configuration the experiment needs a remote SDN controller to be available under the Address 

To start the experiment with the default values set for the variables you can just execute the included script `sdn_topology.py` like this:

```shell
sudo python ./sdn_topology.py
```

To get an explanation of the available options and flags and their default values of the CLI just use:

```shell
python ./sdn_topology.py --help
```

## Structure and Design
The script `sdn_topology.py` initializes the experiment with a Mininet-Wifi topology.
The script `flexible_sdn.py` is run in the nodes of that topology and contains the actual approach of this project.
After running the experiment the main script directly executes evaluation scripts which produce statistic summaries and plots.
Statistics and plots of each run are saved in a new directory under `./data/statistics/`.
The directory will be named with the date and time of the start of the experiment.

The mobility patterns can be found in CSV files under `./data/`.
The mobility patterns that can be used through the CLI of `sdn_topology.py` are in the files `Scenario_*.csv`

The scripts `eval_ditg.py` and `eval_statistics.py` are used to evaluate the statistics after running the experiment.
The output of those are needed to plot the results with `plot_statistics.py` or `plot_animated.py`.

`scanner.py` contains the Multiprocessing class that is used inside the nodes to scan for the AP.
`cmd_utils.py` contains some wrapper functions for the shell commands of `iw dev`.
`sta1-wlan0-olsrd.conf` and `sta3-wlan0-olsrd.conf` contain the configurations needed to start OLSRd. 

### Design
The approach that we implemented in `flexible_sdn.py` is designed as follows:

The basic idea behind our solution is that devices follow SDN policies as long as they are connected to the SDN infrastructure including a controller and an access point connecting the controller with the other nodes and the nodes among each other. 
If this infrastructure is not available to the nodes because of alink disconnection they switch to using a MANET avoiding disruptions of data flows. 
Switching betweenSDN and MANET is managed by a control mechanism which can be run in the nodes of a SDTN and thereby control the network interfaces of the respective node.

![Activity Diagram](/doc/activity-diagram.png)

An activity diagram is shown in Figure illustrating the different states and the activity flow of the control mechanism. 
In the diagram the state of the respective node is represented by the four lanes. 
The node can either be connected to the SDN infrastructure, switch from a SDN connection to MANET, be connected to a MANET or switch from a MANET connection to SDN. 
For the diagram it is assumed that the node is connected to the access point and the SDN controller in the beginning. 
Therefore, the start point is located in the top lane during representing the state in which the node is connected to the SDN although the activity flow is a loop and could start in any of the two connected states.

To detect a disruption of the node from the SDN infrastructure the control mechanism has to monitor the network state.
The connection to the SDN infrastructure is given by the wireless link to the access point in our use case scenario.
Therefore, we choose to monitor the received signal strength of the access point as an indicator for a controller disruption.

The state in which the node is connected to the SDN infrastructure and the control mechanism monitors the signal can be found in the top lane of the activity diagram.
The signal monitor takes the Received Signal Strength Indicator (RSSI) of the access point as a measurement every second and calculates a moving average of a fixed number of measurements where the number of measurements taken for the moving average is defined by a variable `WindowSigAvg`.
The moving average is used instead of the raw measurements because the raw measurements are values of a stochastic process with a variance and outlier values disturb the control mechanism.
This risk of disturbance by outliers can be reduced by using the moving average for the monitoring.

The moving average is compared to a threshold value `Threshold_SigSDN` which is the minimum signal strength expected to provide a reliable connection.
Then the control mechanism can switch from SDN to MANET when the latest average signal is too weak to be sufficiently reliable.
Which signal strength is considered to be reliable depends on the wireless technology.
The value might vary for different technologies like VHF or UHF which are common in TNs and thus the `Threshold_SigSDN` can be changed depending on that.

For switching the network from SDN to MANET the node enters a handover state depicted in the second lane of the activity diagram.
During the handover the node activates a scanner, shapes the data flow and reconfigures its network interface to disconnect from the access point and connect to the MANET.
The scanner is needed to monitor the signal strength of the access point to decide when to switch back to theSDN when the node is connected to the MANET.
The shaping is needed to reduce packet loss during the handover.

Between the disconnection from the access point and the connection to the MANET a gap in the connectivity is inevitable if only one network interface is used for both.
With an active data flow this leads to packet loss.
To minimize the packet loss at this point the control mechanism reduces the outgoing data rate before the handover and increases it back to the normal value after the handover.
The value `Bandwidth_qdisc` to which the data rate is reduced can be configured.
By reducing the outbound data rate during the handover the number of outgoing packets during that time is reduced as well which reduces the number of lost packets.
A Queuing Discipline (qdisc) is used by the control mechanism for the shaping.

The scanner activated during the handover is used during the MANET connection state which can be found in the third lane of the diagram.
Since the node has no active connection to the access point in this state the signal strength can not be monitored as simple as before.
The control mechanism has to scan actively for the SSID of the access point to get measurements of the signal strength.
This is done by the scanner on a second wireless network interface because active scanning blocks the interface.
Therefore,it would cause packet loss if it was executed on the primary interface.

When the node is connected to the MANET the scanner periodically triggers scans for the access point on the second interface.
The scan interval `Interval_Scan` given in seconds can be freely configured but should not be too short since completing a scan can take multiple seconds.
The state of the node being connected to the MANET can be found in the third lane of the activity diagram.
In this state the control mechanism continues to take a measurement of the signal strength every second and to calculate a moving average based on the latest measurements inside the moving average `Window_SigAvg`.

The moving average of the signal is then again used by the control mechanism to decide when to switch the network.
Another threshold `Threshold_SigMANET` is used here as a minimum signal strength that is considered strong enough for a reliable connection.
It can be configured depending on the wireless technology that is used as explained above.
This threshold should be equal or higher than the `Threshold_SigSDN` to avoid a loop of handovers between the two networks when the measured signal is between the two thresholds.

When the value of the measured signal is higher than the `Threshold_SigMANET` the control mechanism enters the handover state represented in the bottom lane of the diagram switching from MANET to SDN.
The activity flow during this handover is the reverse of the handover in the other direction described above.
The scanner is deactivated and in parallel the network interface is reconfigured to disconnect from the MANET and connect to the access point.
Before the disconnection from the MANET and after the connection to the access point is established the data flow is shaped using a qdisc to reduce packet loss in the same way as during the first handover.
The outbound data rate is set to the same value given by `Bandwidth_qdisc` during this handover.
