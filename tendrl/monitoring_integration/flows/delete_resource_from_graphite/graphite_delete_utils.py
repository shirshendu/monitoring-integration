import datetime
import etcd
import os

from tendrl.commons.utils import etcd_utils
from tendrl.monitoring_integration.grafana import utils
from tendrl.monitoring_integration.graphite.graphite_utils import \
    archive
from tendrl.monitoring_integration.graphite.graphite_utils import \
    get_data_dir_path


def update_graphite(integration_id, resource_name, resource_type):
    whisper_path = get_data_dir_path()
    if whisper_path:
        if resource_type == "volume":
            delete_volume_details(
                integration_id,
                resource_name,
                whisper_path,
                resource_type
            )
        if resource_type == "brick":
            delete_brick_details(
                integration_id,
                resource_name,
                whisper_path,
                resource_type
            )
        if resource_type == "host":
            delete_host_details(
                integration_id,
                resource_name,
                whisper_path,
                resource_type
            )


def delete_brick_details(
    integration_id, resource_name, whisper_path, resource_type
):
    # Remove brick details under nodes from graphite
    host_name = resource_name.split(
        "|", 1)[1].split(":", 1)[0].replace(".", "_")
    brick_name = resource_name.split("|", 1)[1].split(
        ":", 1)[1].replace("/", "|")
    vol_name = resource_name.split("|", 1)[0]
    archive_base_path = os.path.join(
        whisper_path,
        "clusters",
        str(integration_id),
        "archive",
        "bricks"
    )
    archive_time = str(
        datetime.datetime.now().isoformat()
    ).replace(".", ":")
    if not os.path.exists(archive_base_path):
        os.makedirs(
            str(archive_base_path)
        )
    archive_path = os.path.join(
        archive_base_path,
        str(brick_name) + "_" + archive_time
    )
    resource_path = os.path.join(
        whisper_path,
        "clusters",
        str(integration_id),
        "nodes",
        str(host_name),
        "bricks",
        str(brick_name)
    )
    brick_path = os.path.join(
        whisper_path,
        "clusters",
        str(integration_id),
        "nodes",
        str(host_name),
        "bricks",
        str(brick_name)
    )
    if os.path.exists(brick_path):
        archive(
            resource_path,
            archive_path,
            resource_name,
            resource_type
        )

    # Remove brick details under volumes from graphite
    archive_path = os.path.join(
        archive_base_path,
        str(brick_name) + "_" + archive_time,
        "volumes",
        vol_name
    )
    os.makedirs(str(archive_path))
    archive_path = os.path.join(
        archive_base_path,
        str(brick_name) + "_" + archive_time,
        "volumes",
        vol_name
    )
    resource_path = os.path.join(
        whisper_path,
        "clusters",
        str(integration_id),
        "volumes",
        str(vol_name),
        "nodes",
        str(host_name),
        "bricks",
        str(brick_name)
    )
    brick_path = os.path.join(
        whisper_path,
        "clusters",
        str(integration_id),
        "volumes",
        str(vol_name),
        "nodes",
        str(host_name),
        "bricks",
        str(brick_name)
    )
    if os.path.exists(brick_path):
        archive(
            resource_path,
            archive_path,
            resource_name,
            resource_type
        )


def delete_volume_details(
    integration_id,
    resource_name,
    whisper_path,
    resource_type
):
    resource_path = os.path.join(
        whisper_path,
        "clusters",
        str(integration_id),
        "volumes",
        resource_name
    )
    archive_path = os.path.join(
        whisper_path,
        "clusters",
        str(integration_id),
        "archive",
        "volumes"
    )
    if not os.path.exists(archive_path):
        os.makedirs(str(archive_path))
    resource_folder_name = str(resource_name) + "_" + \
        str(datetime.datetime.now().isoformat()).replace(".", ":")
    archive_path = os.path.join(
        archive_path,
        resource_folder_name
    )
    if os.path.exists(resource_path):
        archive(
            resource_path,
            archive_path,
            resource_name,
            resource_type
        )


def delete_host_details(
    integration_id,
    resource_name,
    whisper_path,
    resource_type
):
    volume_affected_list = []
    try:
        volume_affected_list = []
        bricks_key = "/clusters/%s/Bricks/all/%s" % (
            integration_id,
            resource_name
        )
        bricks = utils.get_resource_keys("", bricks_key)
        for brick in bricks:
            volume_key = os.path.join(
                bricks_key,
                brick,
                "vol_name"
            )
            volume_name = etcd_utils.read(volume_key).value
            volume_affected_list.append(volume_name)
    except etcd.EtcdKeyNotFound:
        pass
    remove_host(
        integration_id,
        whisper_path,
        resource_name,
        resource_type,
        volume_affected_list
    )


def remove_host(
    integration_id,
    whisper_path,
    resource_name,
    resource_type,
    volume_affected_list
):
    host_name = resource_name.replace(".", "_")
    # remove node from graphite
    archive_path = os.path.join(
        whisper_path,
        "clusters",
        str(integration_id),
        "archive",
        "nodes"
    )
    if not os.path.exists(archive_path):
        os.makedirs(str(archive_path))
    resource_folder_name = str(host_name) + "_" + \
        str(datetime.datetime.now().isoformat().replace(".", ":"))
    archive_path = os.path.join(archive_path, resource_folder_name)
    os.makedirs(str(archive_path))
    resource_path = os.path.join(
        whisper_path,
        "clusters",
        str(integration_id),
        "nodes",
        str(host_name)
    )
    if os.path.exists(resource_path):
        archive(
            resource_path,
            archive_path,
            resource_name,
            resource_type
        )
    # Remove node info under volume from graphite
    for vol_name in volume_affected_list:
        archive_path = os.path.join(
            archive_path,
            "volumes",
            vol_name
        )
        os.makedirs(str(archive_path))
        resource_path = os.path.join(
            whisper_path,
            "clusters",
            str(integration_id),
            "volumes",
            str(vol_name),
            "nodes",
            str(host_name)
        )
        if os.path.exists(resource_path):
            archive(
                resource_path,
                archive_path,
                resource_name,
                resource_type
            )
