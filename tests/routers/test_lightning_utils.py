from app.models.lightning import LightningInfoLite


def get_valid_lightning_info_lite() -> LightningInfoLite:
    return LightningInfoLite(
        implementation="LND",
        version="0.13.1",
        identity_pubkey="0246ad12eb40bcf26a0cd50757b15a58181d0ad0d78d5bc31e8058205321c3e632",
        num_pending_channels=1,
        num_active_channels=4,
        num_inactive_channels=2,
        num_peers=3,
        block_height=123456,
        synced_to_chain=True,
        synced_to_graph=True,
    )
