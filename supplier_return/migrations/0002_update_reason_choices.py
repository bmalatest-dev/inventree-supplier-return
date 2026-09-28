from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("supplier_return", "0001_initial")]
    operations = [
        migrations.AlterField(
            model_name="supplierreturnline",
            name="reason",
            field=models.CharField(
                choices=[
                    ("DEFECTIVE", "Defective / Failed Inspection"),
                    ("INCORRECT", "Incorrect Item"),
                    ("INCORRECT_QTY", "Incorrect Quantity"),
                    ("DAMAGED", "Damaged"),
                    ("NOT_REQUIRED", "No Longer Required"),
                    ("ORDERED_ERROR", "Ordered in Error"),
                    ("OTHER", "Other"),
                ],
                max_length=32,
            ),
        ),
    ]
