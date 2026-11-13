// SPDX-License-Identifier: GPL-2.0
/*
 * Read-only dump of the SANV ACPI NVS block at 0x44A52D18.
 * Tries ACPICA mapping first, then ioremap cache-mode variants.
 * No writes to NVS.
 */
#include <linux/module.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/memremap.h>

#define SANV_PHYS 0x44A52D18UL
#define SANV_LEN  0x1BC

/* Exported by drivers/acpi/osl.c (GPL). */
extern void __iomem *acpi_os_map_memory(u64 phys, u64 size);
extern void acpi_os_unmap_memory(void __iomem *virt, u64 size);

static u8 sanv[SANV_LEN];

static u32 le32(const u8 *p)
{
	return (u32)p[0] | ((u32)p[1] << 8) | ((u32)p[2] << 16) | ((u32)p[3] << 24);
}

static void dump(const char *how)
{
	u32 hrg0 = le32(sanv + 0x08c);
	u32 pwg0 = le32(sanv + 0x092);
	u32 rpba = le32(sanv + 0x12f);
	u16 pvid = 0xffff, pdid = 0xffff;

	if (rpba) {
		void __iomem *cfg = ioremap(rpba, 4);
		if (cfg) {
			pvid = readw(cfg);
			pdid = readw(cfg + 2);
			iounmap(cfg);
		}
	}

	pr_info("sanv_read[%s]: HGMD=0x%02x HGFL=0x%02x SGGP=0x%02x\n",
		how, sanv[0x088], sanv[0x089], sanv[0x08a]);
	pr_info("sanv_read[%s]: HRE0=0x%02x HRG0=0x%08x HRA0=0x%02x PWE0=0x%02x PWG0=0x%08x PWA0=0x%02x\n",
		how, sanv[0x08b], hrg0, sanv[0x090], sanv[0x091], pwg0, sanv[0x096]);
	pr_info("sanv_read[%s]: RPBA=0x%08x PVID=0x%04x PDID=0x%04x\n",
		how, rpba, pvid, pdid);
	pr_info("sanv_read[%s]: raw 0x88..0x98: %*ph\n", how, 17, sanv + 0x088);
}

static int __init sanv_read_init(void)
{
	void __iomem *map = NULL;
	const char *how = NULL;

	map = acpi_os_map_memory(SANV_PHYS, SANV_LEN);
	if (map) {
		how = "acpi_os_map_memory";
		memcpy_fromio(sanv, map, SANV_LEN);
		acpi_os_unmap_memory(map, SANV_LEN);
		goto got;
	}
	pr_info("sanv_read: acpi_os_map_memory failed\n");

	map = ioremap_cache(SANV_PHYS, SANV_LEN);
	if (map) {
		how = "ioremap_cache";
		memcpy_fromio(sanv, map, SANV_LEN);
		iounmap(map);
		goto got;
	}
	pr_info("sanv_read: ioremap_cache failed\n");

	map = ioremap_wc(SANV_PHYS, SANV_LEN);
	if (map) {
		how = "ioremap_wc";
		memcpy_fromio(sanv, map, SANV_LEN);
		iounmap(map);
		goto got;
	}
	pr_info("sanv_read: ioremap_wc failed\n");

	map = ioremap_uc(SANV_PHYS, SANV_LEN);
	if (map) {
		how = "ioremap_uc";
		memcpy_fromio(sanv, map, SANV_LEN);
		iounmap(map);
		goto got;
	}
	pr_info("sanv_read: ioremap_uc failed\n");

	{
		void *m = memremap(SANV_PHYS, SANV_LEN, MEMREMAP_WB);
		if (m) {
			how = "memremap_wb";
			memcpy(sanv, m, SANV_LEN);
			memunmap(m);
			goto got;
		}
	}
	pr_info("sanv_read: memremap_wb failed\n");

	pr_err("sanv_read: every mapping method failed\n");
	return -ENOMEM;

got:
	dump(how);
	return 0;
}

static void __exit sanv_read_exit(void) {}

module_init(sanv_read_init);
module_exit(sanv_read_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only SANV ACPI NVS dump");
