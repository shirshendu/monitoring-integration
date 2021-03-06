import copy
import json
import os

from tendrl.commons.utils import log_utils as logger
from tendrl.monitoring_integration.grafana import alert_utils
from tendrl.monitoring_integration.grafana import constants
from tendrl.monitoring_integration.grafana import utils


def set_alert(panel, thresholds, severity, resource_name, title):
    if severity.lower() == "critical":
        panel["thresholds"] = [
            {"colorMode": "critical",
             "fill": True,
             "line": True,
             "op": "gt",
             "value": thresholds[severity]
             }
        ]
        panel["alert"] = ({"conditions": [
            {"evaluator": {"params": [thresholds[severity]], "type": "gt"},
             "operator": {"type": "and"},
             "query": {"params": [panel["targets"][-1]["refId"], "3m", "now"]},
             "reducer": {"params": [], "type": "avg"},
             "type": "query"
             }],
            "executionErrorState": "keep_state",
            "frequency": "60s", "handler": 1,
            "name": str(resource_name) + " " + str(title) + " Alert",
            "noDataState": "keep_state",
            "notifications": []}
        )
    else:
        panel["thresholds"] = [
            {"colorMode": "critical",
             "fill": True,
             "line": True,
             "op": "gt",
             "value": thresholds[severity]
             },
            {"colorMode": "critical",
             "fill": True,
             "line": True,
             "op": "lt",
             "value": thresholds["Critical"]
             }
        ]
        panel["alert"] = (
            {"conditions": [
                {"evaluator": {"params": [thresholds[severity],
                                          thresholds["Critical"]],
                               "type": "within_range"},
                 "operator": {"type": "and"},
                 "query": {"params": [panel["targets"][-1]["refId"],
                                      "3m",
                                      "now"]},
                 "reducer": {"params": [], "type": "avg"},
                 "type": "query"
                 }],
             "executionErrorState": "keep_state",
             "frequency": "60s", "handler": 1,
             "name": str(resource_name) + " " + str(title) + " Alert",
             "noDataState": "keep_state",
             "notifications": []
             }
        )


def get_panels(resource_rows):

    new_resource_panel = []
    try:
        for row in resource_rows:
            panels = row["panels"]
            for panel in panels:
                if panel["type"] == "graph":
                    new_resource_panel.append(copy.deepcopy(panel))
    except (KeyError, AttributeError) as ex:
        logger.log("debug", NS.get("publisher_id", None),
                   {'message': "Error in retrieving resource "
                   "rows (get_panel) " + str(ex)})
    return new_resource_panel


def set_gluster_target(target, integration_id, resource, resource_name):

    target["target"] = target["target"].replace('$interval', '1m')
    target["target"] = target["target"].replace('$my_app', 'tendrl')
    target["target"] = target["target"].replace(
        '$cluster_id', str(integration_id))
    if resource_name == "volumes":
        target["target"] = target["target"].replace('$volume_name',
                                                    str(resource["name"]))
        new_title = str(resource["name"])
    elif resource_name == "hosts":
        target["target"] = target["target"].replace(
            '$host_name',
            str(resource["fqdn"].replace(".", "_")))
        new_title = str(resource["fqdn"].replace(".", "_"))
    elif resource_name == "bricks":
        target["target"] = target["target"].replace(
            '$host_name',
            str(resource["hostname"].replace(".", "_")))
        target["target"] = target["target"].replace(
            '$brick_path',
            str(resource["brick_path"]))
        target["target"] = target["target"].replace('$volume_name',
                                                    str(resource["vol_name"]))
        new_title = str(resource["vol_name"] + "-" + resource[
            "hostname"].replace(".", "_")) + \
            "-" + str(resource["brick_path"])
    if "alias" in target["target"] and "aliasByNode" not in target["target"]:
        target["target"] = target["target"].split('(', 1)[-1].rsplit(',', 1)[0]
    return new_title


def create_resource_dashboard(
    resource_name, resource, sds_name, integration_id
):
    dashboard_path = constants.PATH_PREFIX + constants.DASHBOARD_PATH + \
        "/tendrl-" + str(sds_name) + "-" + str(resource_name) + '.json'

    if os.path.exists(dashboard_path):
        resource_file = utils.fread(dashboard_path)
        try:
            new_title = ""
            resource_json = json.loads(resource_file)
            resource_json["dashboard"]["title"] = "Alerts - " + \
                str(resource_json["dashboard"]["title"])
            resource_rows = resource_json["dashboard"]["rows"]
            global_row = {"collapse": False,
                          "height": 250,
                          "panels": [],
                          "repeat": None,
                          "repeatIteration": None,
                          "repeatRowId": None,
                          "showTitle": False,
                          "title": "Dashboard Row",
                          "titleSize": "h6"
                          }
            new_resource_panel = get_panels(resource_rows)
            alert_thresholds = NS.monitoring.definitions.get_parsed_defs()[
                "namespace.monitoring"]["thresholds"][resource_name]
            all_resource_rows = []
            count = 1
            global_row["panels"] = []
            panel_count = 1
            for panel in new_resource_panel:
                try:
                    new_title = ""
                    for panel_title in alert_thresholds:
                        if not panel["title"].lower().find(
                                panel_title.replace("_", " ")):
                            targets = panel["targets"]
                            for target in targets:
                                if sds_name == constants.GLUSTER:
                                    new_title = set_gluster_target(
                                        target,
                                        integration_id,
                                        resource,
                                        resource_name
                                    )
                                else:
                                    # In future need to add ceph target
                                    pass
                            panel["legend"]["show"] = False
                            title = panel["title"]
                            for severity in constants.ALERT_SEVERITY:
                                set_alert(
                                    panel,
                                    alert_thresholds[panel_title],
                                    severity,
                                    resource_name,
                                    title + "-" + severity
                                )
                                panel["title"] = title + "-" + str(
                                    new_title) + "-" + severity
                                panel["id"] = count
                                # For better visibility,
                                # 7 panels per row is created
                                if panel_count < constants.MAX_PANELS_IN_ROW:
                                    global_row["panels"].append(
                                        copy.deepcopy(panel)
                                    )
                                    panel_count = panel_count + 1
                                else:
                                    global_row["panels"].append(panel)
                                    all_resource_rows.append(
                                        copy.deepcopy(global_row))
                                    global_row["panels"] = []
                                    panel_count = 1
                                count = count + 1
                except KeyError as ex:
                    logger.log(
                        "error",
                        NS.get("publisher_id", None),
                        {'message': str(panel[
                            "title"]) + "failed" + str(ex)}
                    )
            if global_row["panels"]:
                all_resource_rows.append(copy.deepcopy(global_row))
            if len(all_resource_rows) > 0:
                resource_json["dashboard"]["rows"] = []
                resource_json["dashboard"]["rows"] = all_resource_rows
                resource_json["dashboard"]["templating"] = {}
                resp = alert_utils.post_dashboard(resource_json)
                if resp.status_code == 200:
                    msg = ("Alert dashboard for %s-%s is created " +
                           "successfully") % (resource_name, new_title)
                    logger.log("debug", NS.get("publisher_id", None),
                               {'message': msg})
                else:
                    msg = "Alert dashboard upload failed for %s-%s" % \
                          (resource_name, new_title)
                    logger.log("debug", NS.get("publisher_id", None),
                               {'message': msg})
        except Exception as ex:
            logger.log("debug", NS.get("publisher_id", None),
                       {'message': str(ex)})


def add_panel(integration_id, resource_type, resource_name, sds_name):
    resp = None
    alert_dashboard = alert_utils.get_alert_dashboard(
        resource_type
    )
    if alert_dashboard:
        try:
            if alert_dashboard["message"] == "Dashboard not found":
                flag = False
            else:
                flag = True
        except (KeyError, AttributeError):
            flag = True
        if flag:
            try:
                if sds_name == constants.GLUSTER:
                    # check duplicate rows
                    if not check_duplicate(
                        alert_dashboard,
                        integration_id,
                        resource_type,
                        resource_name
                    ):
                        alert_row = fetch_row(alert_dashboard)
                        add_gluster_resource_panel(
                            alert_row,
                            integration_id,
                            resource_type,
                            resource_name
                        )
                        dash_json = create_updated_dashboard(
                            alert_dashboard, alert_row
                        )
                        resp = alert_utils.post_dashboard(dash_json)
            except Exception as ex:
                logger.log("error", NS.get("publisher_id", None),
                           {'message': "Error while updating "
                            "dashboard for %s" % resource_name})
                raise ex
    return resp


def check_duplicate(
    alert_dashboard, integration_id, resource_type, resource
):
    existing_reource = False
    for row in alert_dashboard["dashboard"]["rows"]:
        if "panels" in row and (not existing_reource):
            for target in row["panels"][0]["targets"]:
                resource_name = resource
                if resource_name is not None:
                    if str(integration_id) in target["target"]:
                        if resource_type == "volumes":
                            # tendrl.clusters.{cid}.volumes.{vol_name}.pcnt_used
                            vol_name = target["target"].split(
                                "volumes."
                            )[1].split(".")[0]
                            if resource_name == vol_name:
                                existing_reource = True
                                break
                        elif resource_type == "bricks":
                            # tendrl.clusters.{cid}.nodes.{h_name}.bricks.{path}.
                            # utilization.percent-percent_bytes
                            hostname = resource_name.split(":")[0].split(
                                "|")[1].replace(".", "_")
                            resource_name = resource_name.split(
                                ":", 1)[1].replace("/", "|")
                            host = target["target"].split(
                                "nodes."
                            )[1].split(".")[0]
                            brick_path = target["target"].split(
                                "bricks."
                            )[1].split(".")[0]
                            if hostname == host and \
                                    resource_name == brick_path:
                                existing_reource = True
                                break
                        elif resource_type == "hosts":
                            # tendrl.clusters.{cid}.nodes.{host_name}.
                            # {memory/cpu/swap}.*
                            host_name = target["target"].split(
                                "nodes."
                            )[1].split(".")[0]
                            if resource_name == host_name:
                                existing_reource = True
                                break
                elif str(integration_id) in target["target"]:
                    existing_reource = True
                    break
        elif existing_reource:
            break
    return existing_reource


def add_gluster_resource_panel(
    alert_rows, integration_id, resource_type, resource_name
):
    if resource_type == "hosts":
        resource_type = "nodes"
    for alert_row in alert_rows:
        panel_count = alert_row["panels"][-1]["id"] + 1
        for panel in alert_row["panels"]:
            targets = panel["targets"]
            for target in targets:
                try:
                    if resource_type == "bricks":
                        panel_target = ("tendrl" + target["target"].split(
                            "tendrl")[1].split(")")[0]).split(".")
                        old_integration_id = panel_target[
                            panel_target.index("clusters") + 1]
                        target["target"] = target["target"].replace(
                            old_integration_id, str(integration_id))
                        if "volumes" in panel_target:
                            old_resource_name = panel_target[
                                panel_target.index("volumes") + 1]
                            target["target"] = target["target"].replace(
                                old_resource_name,
                                str(resource_name.split("|", 1)[0]))
                        if "nodes" in panel_target:
                            old_resource_name = panel_target[
                                panel_target.index("nodes") + 1]
                            target["target"] = target["target"].replace(
                                old_resource_name,
                                str(resource_name.split("|", 1)[1].split(
                                    ":", 1)[0].replace(".", "_")))
                        if "bricks" in panel_target:
                            old_resource_name = panel_target[
                                panel_target.index("bricks") + 1]
                            target["target"] = target["target"].replace(
                                old_resource_name,
                                str(resource_name.split("|", 1)[1].split(
                                    ":", 1)[1].replace("/", "|")))
                    else:
                        panel_target = ("tendrl" + target["target"].split(
                            "tendrl")[1].split(")")[0]).split(".")
                        old_integration_id = panel_target[
                            panel_target.index("clusters") + 1]
                        target["target"] = target["target"].replace(
                            old_integration_id, str(integration_id))
                        if resource_name is not None:
                            old_resource_name = panel_target[
                                panel_target.index(str(resource_type)) + 1]
                            target["target"] = target["target"].replace(
                                old_resource_name, str(resource_name))
                except (KeyError, IndexError):
                    pass
            panel["id"] = panel_count
            panel_count = panel_count + 1
            new_title = resource_name
            if resource_type == "bricks":
                host_name = resource_name.split("|", 1)[1].split(
                    ":", 1)[0].replace(".", "_")
                brick_name = resource_name.split("|", 1)[1].split(
                    ":", 1)[1].replace("/", "|")
                volume_name = resource_name.split("|", 1)[0]
                new_title = volume_name + "|" + host_name + ":" + brick_name
            panel["title"] = panel["title"].split(
                "-", 1)[0] + "-" + str(
                    new_title) + "-" + panel["title"].split("-")[-1]


def fetch_row(dashboard_json):

    rows = dashboard_json["dashboard"]["rows"]
    if len(rows) > 1:
        for count in xrange(1, len(rows)):
            if rows[0]["panels"][0]["title"].split("-", 1)[0] == \
                    rows[count]["panels"][0]["title"].split("-", 1)[0]:
                alert_row = copy.deepcopy(
                    dashboard_json["dashboard"]["rows"][-count:])
                break
    else:
        alert_row = [copy.deepcopy(dashboard_json["dashboard"]["rows"][-1])]
    return alert_row


def create_updated_dashboard(dashboard_json, alert_rows):
    dashboard_json["dashboard"]["rows"] = dashboard_json[
        "dashboard"]["rows"] + alert_rows
    return dashboard_json
