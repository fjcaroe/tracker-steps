from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPreliquidationPrice(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.season = cls.env["step.temporada"].create({"name": "Temporada T38"})
        cls.species = cls.env["step.especie"].create({
            "name": "Cerezas T38", "type_especie": "frutal", "group_especie": "baya",
        })
        group = cls.env["step.grupo.variedad"].create({
            "name": "Cerezas T38", "especie_id": cls.species.id,
        })
        cls.variety = cls.env["step.variedad"].create({
            "name": "Santina T38", "cod_variedad": "T38-SANTINA",
            "especie_id": cls.species.id, "grupo_variedad_id": group.id,
        })
        cls.uom = cls.env.ref("uom.product_uom_kgm")
        cls.product = cls.env["product.product"].create({"name": "Fruta T38"})
        cls.price_list = cls.env["step.producer.preliq.price"].create({
            "name": "Precios T38", "season_id": cls.season.id,
            "species_id": cls.species.id, "valid_from": "2026-07-01",
            "valid_to": "2026-12-31",
            "line_ids": [
                (0, 0, {"variety_id": cls.variety.id, "uom_id": cls.uom.id, "price": 5.5}),
                (0, 0, {"variety_id": cls.variety.id, "uom_id": cls.uom.id,
                        "product_id": cls.product.id, "price": 6.3}),
            ],
        })

    def test_especifico_prevalece_sobre_precio_general(self):
        resolver = self.env["step.producer.preliq.price"].resolve_price
        args = (self.env.company, self.season, self.species, self.variety, "2026-11-12")
        self.assertEqual(resolver(*args, uom=self.uom).price, 5.5)
        self.assertEqual(resolver(*args, product=self.product, uom=self.uom).price, 6.3)

    def test_ambiguedad_y_fecha_fuera_de_vigencia(self):
        self.env["step.producer.preliq.price.line"].create({
            "price_id": self.price_list.id, "variety_id": self.variety.id,
            "uom_id": self.uom.id, "price": 5.8,
        })
        resolver = self.env["step.producer.preliq.price"].resolve_price
        args = (self.env.company, self.season, self.species, self.variety)
        with self.assertRaises(UserError):
            resolver(*args, "2026-11-12", uom=self.uom)
        with self.assertRaises(UserError):
            resolver(*args, "2027-01-01", uom=self.uom)

    def test_tariff_cost_prefers_producer_and_rejects_equal_concepts(self):
        producer = self.env["res.partner"].create({"name": "Los Cedros T38"})
        other = self.env["res.partner"].create({"name": "Otro productor T38"})
        item = self.env["step.export.grower.discount"].create({
            "name": "Costos T38",
        })
        rates = self.env["step.export.grower.rate"]
        rates.create({
            "name": "General T38", "company_id": self.env.company.id,
            "season_id": self.season.id, "species_id": self.species.id,
            "preliq_line_ids": [(0, 0, {
                "item_id": item.id, "value": 1.0,
            })],
        })
        specific = rates.create({
            "name": "Los Cedros T38", "company_id": self.env.company.id,
            "producer_id": producer.id, "season_id": self.season.id,
            "species_id": self.species.id,
            "preliq_line_ids": [(0, 0, {
                "item_id": item.id, "value": 2.06,
            })],
        })
        args = (self.env.company, self.season, self.species, producer,
                self.variety, self.product, 5.5)
        self.assertAlmostEqual(rates.resolve_preliq_cost(*args), 2.06)
        self.assertAlmostEqual(rates.resolve_preliq_cost(
            self.env.company, self.season, self.species, other,
            self.variety, self.product, 5.5), 1.0)
        specific.preliq_line_ids = [(0, 0, {
            "item_id": item.id, "value": 2.5,
        })]
        with self.assertRaisesRegex(UserError, "igual de específicos"):
            rates.resolve_preliq_cost(*args)
